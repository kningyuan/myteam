"""对话服务 — 编排 Agent 身份、规则、Session、Adapter。"""

import os
import sys
from pathlib import Path
from threading import Event
from typing import Generator, Optional

# 确保工程根在 path
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import adapter as _adapter  # noqa: F401  — side-effect CLI 注册 — 注册 CLI 实例
from adapter.core.events import EventKind
from adapter.core.protocol import RunRequest
from adapter.core.registry import registry
from adapter.core.sse import encode_done, encode_error, encode_event
from common.agent.agent_execution import agent_execution_lock
from common.gate.rules_merge import RulesProfile, merge_rules_file, normalize_rules_profile
from common.paths import RULES_DIR, resolve_workspace
from config_store.sessions import session_store
from base.agent_identity import AgentIdentityBuilder, multi_agent_manager
from base.agent_chat import get_agent_backend_config, _load_agents_config
from common.agent.agent_skills import build_skill_context
from common.agent.agent_mcp import build_mcp_context


class ChatService:
    """1-on-1 Agent 对话 — 唯一入口调用 Adapter。"""

    def stream(
        self,
        agent_id: str,
        message: str,
        cancel_event: Optional[Event] = None,
        *,
        use_memory: bool = False,
        rules_profile: RulesProfile = "interactive",
        workspace_key: Optional[str] = None,
        memory_scope=None,
    ) -> Generator[str, None, None]:
        """1-on-1 流式对话。

        use_memory=True（DM 路径，P0）：对话历史进 Store、由 Context Assembler 组装上下文，
        own-history、不依赖 opencode -s。其余调用方（群组/通知/工厂）保持 use_memory=False 旧路径。
        rules_profile：interactive=私聊/群聊交互任务；discussion=圆桌；workflow_execute=编排 execute。
        workspace_key：Adapter session 映射键；默认 workspace-{agent_id}，群/圆桌由 agent_memory 提供。
        memory_scope：外挂记忆作用域；若提供则 before/after_turn 由 provider 处理。
        """
        profile = normalize_rules_profile(rules_profile)  # type: ignore[arg-type]
        with agent_execution_lock(agent_id, blocking=False) as acquired:
            if not acquired:
                yield encode_error("Agent 正在执行编排任务，请稍后再试")
                return
            if use_memory:
                yield from self._stream_memory(
                    agent_id, message, cancel_event, rules_profile=profile,
                )
                return
        from memstack.facade import after_chat_turn, on_chat_turn
        from memstack.l1.protocol import MemoryScope, memory_scope_dm
        from memstack.l1.registry import get_agent_memory_provider
        from memstack.orchestration.context import ChatTurnContext

        scope = memory_scope if isinstance(memory_scope, MemoryScope) else memory_scope_dm(agent_id)
        provider = get_agent_memory_provider()
        effective_message = on_chat_turn(
            ChatTurnContext(scope=scope, message=message, owner_id=agent_id),
            provider=provider,
        )
        agent_cfg = _load_agents_config().get(agent_id, {})
        workspace = resolve_workspace(agent_id, agent_cfg.get("workspace"))
        if not workspace.is_dir():
            yield encode_error(f"Agent '{agent_id}' 的工作目录不存在")
            return

        backend_cfg = get_agent_backend_config(agent_id)
        adapter = registry.get(backend_cfg.backend_id)
        if not adapter:
            yield encode_error(f"Adapter '{backend_cfg.backend_id}' 未注册")
            return

        model = backend_cfg.model
        rules_file = self._merge_rules(agent_id, str(workspace), profile=profile)
        system_prompt = self._build_system_prompt(agent_id, str(workspace), profile=profile)
        full_message = (
            f"【系统指令】\n{system_prompt}\n\n【用户消息】\n{effective_message}"
            if system_prompt else effective_message
        )

        adapter_id = backend_cfg.backend_id
        ws_key = workspace_key or provider.session_key(scope)
        session_id = session_store.get(adapter_id, agent_id, ws_key)
        sid = ""
        assistant_buf: list[str] = []

        try:
            has_output = False

            def _run(sess: Optional[str]):
                nonlocal sid, has_output
                req = RunRequest(
                    workspace=str(workspace),
                    message=full_message,
                    model=model,
                    session_id=sess,
                    rules_file=rules_file,
                    agent_id=agent_id,
                    cancel_event=cancel_event,
                )
                for event in adapter.run(req):
                    if event.kind == EventKind.SESSION:
                        sid = event.data.get("session_id", sid)
                        continue
                    if event.kind == EventKind.ERROR:
                        has_output = True
                        yield encode_error(event.data.get("message", ""))
                        return
                    has_output = True
                    encoded = encode_event(event)
                    if encoded:
                        if event.kind == EventKind.TEXT:
                            chunk = (event.data or {}).get("content", "")
                            if chunk:
                                assistant_buf.append(chunk)
                        yield encoded

            yield from _run(session_id)

            if not has_output and session_id and adapter.capabilities.multi_turn:
                session_store.remove(adapter_id, agent_id, ws_key)
                sid = ""
                yield from _run(None)

            if sid:
                session_store.set(adapter_id, agent_id, ws_key, sid)

            try:
                after_chat_turn(
                    scope,
                    message,
                    "".join(assistant_buf).strip(),
                    provider=provider,
                )
            except Exception:
                pass

            yield encode_done(sid)

        finally:
            if rules_file and os.path.exists(rules_file):
                try:
                    os.remove(rules_file)
                except Exception:
                    pass

    def _stream_memory(
        self,
        agent_id: str,
        message: str,
        cancel_event: Optional[Event] = None,
        *,
        rules_profile: str = "interactive",
    ) -> Generator[str, None, None]:
        """DM 记忆路径：消息落库 + Context Assembler 组装上下文 + own-history（无 -s）。"""
        from common.store.store import Store
        from common.prompt.context_assembler import assemble_context, maybe_update_summary

        agent_cfg = _load_agents_config().get(agent_id, {})
        workspace = resolve_workspace(agent_id, agent_cfg.get("workspace"))
        if not workspace.is_dir():
            yield encode_error(f"Agent '{agent_id}' 的工作目录不存在")
            return
        backend_cfg = get_agent_backend_config(agent_id)
        adapter = registry.get(backend_cfg.backend_id)
        if not adapter:
            yield encode_error(f"Adapter '{backend_cfg.backend_id}' 未注册")
            return
        model = backend_cfg.model
        rules_file = self._merge_rules(agent_id, str(workspace), profile=rules_profile)
        system_prompt = self._build_system_prompt(agent_id, str(workspace), profile=rules_profile)

        store = Store()
        try:
            conv_id = store.get_or_create_dm(agent_id)
            store.append_message(conv_id, "user", "user", text=message)

            assembled = assemble_context(store, conv_id, message)
            context = assembled["text"]
            citations = assembled["citations"]
            sections = []
            if system_prompt:
                sections.append(f"【系统指令】\n{system_prompt}")
            if context:
                sections.append(context)
            sections.append(f"【用户消息】\n{message}")
            full_message = "\n\n".join(sections)

            # 引用闭环：先把本轮依据的召回来源推给 UI（落库见下方 parts）
            if citations:
                from adapter.core.sse import encode_citations
                yield encode_citations(citations)

            req = RunRequest(
                workspace=str(workspace),
                message=full_message,
                model=model,
                session_id=None,            # own-history：不依赖 opencode -s，避免历史重复注入
                rules_file=rules_file,
                agent_id=agent_id,
                cancel_event=cancel_event,
            )
            from common.observability.thinking_trace import append_thinking_payload

            buf: list[str] = []
            trace_parts: list[dict] = []
            trace_reply_scratch: list[str] = []
            cancelled = False
            for event in adapter.run(req):
                if cancel_event is not None and cancel_event.is_set():
                    cancelled = True
                    break
                if event.kind == EventKind.SESSION:
                    continue
                if event.kind == EventKind.ERROR:
                    yield encode_error(event.data.get("message", ""))
                    return
                payload = event.to_thinking_payload()
                if payload:
                    if (
                        payload.get("type") == "text"
                        and event.data.get("source") == "result"
                        and buf
                    ):
                        pass
                    else:
                        append_thinking_payload(
                            payload, trace_reply_scratch, trace_parts,
                        )
                if event.kind == EventKind.TEXT:
                    content = event.data.get("content", "") or ""
                    if not content:
                        continue
                    # claude result 行兜底：仅当流中尚无文本时采纳，避免与 assistant 块重复
                    if event.data.get("source") == "result":
                        if not buf:
                            buf.append(content)
                    else:
                        buf.append(content)
                encoded = encode_event(event)
                if encoded:
                    from hub.services.stream_fanout import fanout_stream_event

                    fanout_stream_event(agent_id, encoded)
                    yield encoded

            reply = "".join(buf).strip()
            if reply and not cancelled:
                msg_meta = {"thinking": trace_parts} if trace_parts else None
                store.append_message(
                    conv_id, "agent", agent_id, text=reply,
                    parts=[{"type": "text", "text": reply}] + citations,
                    backend=backend_cfg.backend_id,
                    meta=msg_meta,
                )
            if not cancelled:
                maybe_update_summary(
                    store, conv_id,
                    summarize_fn=self._make_summarizer(adapter, str(workspace), model,
                                                       rules_file, agent_id))
            done_sse = encode_done("")
            from hub.services.stream_fanout import fanout_stream_event

            fanout_stream_event(agent_id, done_sse)
            yield done_sse
        finally:
            store.close()
            if rules_file and os.path.exists(rules_file):
                try:
                    os.remove(rules_file)
                except Exception:
                    pass

    def _make_summarizer(self, adapter, workspace: str, model: str,
                         rules_file: Optional[str], agent_id: str):
        """返回 summarize_fn(pending, prev)->str：用当前 agent「顺带」生成滚动摘要。"""
        def _summarize(pending: list, prev: str) -> str:
            convo = "\n".join(
                f"{m.get('author') or m.get('role')}：{m.get('text', '')}" for m in pending)
            prompt = (
                "请把下面这段对话压缩成简洁的滚动摘要，保留关键事实、决策、待办与用户偏好，"
                "去掉寒暄与冗余。只输出摘要正文。\n"
                + (f"\n【已有摘要】\n{prev}\n" if prev else "")
                + f"\n【新增对话】\n{convo}"
            )
            req = RunRequest(workspace=workspace, message=prompt, model=model,
                             session_id=None, rules_file=rules_file, agent_id=agent_id)
            out: list[str] = []
            for ev in adapter.run(req):
                if ev.kind == EventKind.TEXT:
                    out.append(ev.data.get("content", ""))
            return "".join(out).strip()
        return _summarize

    def _build_system_prompt(
        self, agent_id: str, workspace: str, *, profile: str = "interactive",
    ) -> str:
        builder = AgentIdentityBuilder(agent_id, workspace)
        sections = []
        identity = builder.get_identity_context(rules_profile=profile)
        if identity:
            sections.append(f"<core_instructions>\n{identity}\n</core_instructions>")
        from common.agent.agent_registry import build_registry_capability_context

        registry_block = build_registry_capability_context(agent_id)
        if registry_block:
            sections.append(registry_block)
        skill_block = build_skill_context(agent_id)
        if skill_block:
            sections.append(skill_block)
        try:
            from execution_harness.pre.interactive import build_interactive_harness_block

            harness_block = build_interactive_harness_block(agent_id)
            if harness_block:
                sections.append(harness_block)
        except Exception:
            pass
        mcp_block = build_mcp_context(agent_id)
        if mcp_block:
            sections.append(mcp_block)
        multi = multi_agent_manager.build_multi_agent_context(agent_id)
        if multi:
            sections.append(f"<multi_agent_context>\n{multi}\n</multi_agent_context>")
        return "\n\n".join(sections)

    def _merge_rules(
        self,
        agent_id: str,
        workspace: str,
        *,
        profile: RulesProfile = "interactive",
    ) -> Optional[str]:
        builder = AgentIdentityBuilder(agent_id, workspace)
        return merge_rules_file(
            agent_id,
            workspace,
            RULES_DIR,
            profile=profile,
            chinese_name=builder.extract_chinese_name(),
        )


chat_service = ChatService()
