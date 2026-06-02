"""对话服务 — 编排 Agent 身份、规则、Session、Adapter。"""

import os
import sys
import tempfile
from pathlib import Path
from threading import Event
from typing import Generator, Optional

# 确保工程根在 path
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import adapters  # noqa: F401 — 注册 CLI 实例
from adapter.events import EventKind
from adapter.protocol import RunRequest
from adapter.registry import registry
from adapter.sse import encode_done, encode_error, encode_event
from hub.paths import SKILL_DIR, resolve_workspace
from store.sessions import session_store

# 过渡期：复用 base 的身份与配置
from base.agent_identity import AgentIdentityBuilder, multi_agent_manager
from base.agent_chat import get_agent_backend_config, _load_agents_config


class ChatService:
    """1-on-1 Agent 对话 — 唯一入口调用 Adapter。"""

    def stream(
        self,
        agent_id: str,
        message: str,
        cancel_event: Optional[Event] = None,
    ) -> Generator[str, None, None]:
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

        model = backend_cfg.model or adapter.get_default_model()
        rules_file = self._merge_rules(agent_id, str(workspace))
        system_prompt = self._build_system_prompt(agent_id, str(workspace))
        full_message = (
            f"【系统指令】\n{system_prompt}\n\n【用户消息】\n{message}"
            if system_prompt else message
        )

        adapter_id = backend_cfg.backend_id
        ws_key = f"workspace-{agent_id}"
        session_id = session_store.get(adapter_id, agent_id, ws_key)
        sid = ""

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
                        yield encoded

            yield from _run(session_id)

            if not has_output and session_id and adapter.capabilities.multi_turn:
                session_store.remove(adapter_id, agent_id, ws_key)
                sid = ""
                yield from _run(None)

            if sid:
                session_store.set(adapter_id, agent_id, ws_key, sid)

            yield encode_done(sid)

        finally:
            if rules_file and os.path.exists(rules_file):
                try:
                    os.remove(rules_file)
                except Exception:
                    pass

    def _build_system_prompt(self, agent_id: str, workspace: str) -> str:
        builder = AgentIdentityBuilder(agent_id, workspace)
        sections = []
        identity = builder.get_identity_context()
        if identity:
            sections.append(f"<core_instructions>\n{identity}\n</core_instructions>")
        multi = multi_agent_manager.build_multi_agent_context(agent_id)
        if multi:
            sections.append(f"<multi_agent_context>\n{multi}\n</multi_agent_context>")
        return "\n\n".join(sections)

    def _merge_rules(self, agent_id: str, workspace: str) -> Optional[str]:
        universal = SKILL_DIR / "rule" / "universal-rules.md"
        agents_md = Path(workspace) / "AGENTS.md"
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".md", prefix=f"rules-{agent_id}-", dir="/tmp")
            builder = AgentIdentityBuilder(agent_id, workspace)
            chinese_name = builder.extract_chinese_name()
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(f"# {chinese_name} - 完整规则\n\n")
                if universal.exists():
                    f.write(universal.read_text(encoding="utf-8"))
                    f.write("\n\n---\n\n")
                for name in ["brainstorming-guide.md", "worker-template.md"]:
                    fp = SKILL_DIR / "rule" / name
                    if agent_id != "main" and fp.exists():
                        f.write(fp.read_text(encoding="utf-8"))
                        f.write("\n\n---\n\n")
                if agents_md.exists():
                    f.write(agents_md.read_text(encoding="utf-8"))
            return temp_path
        except Exception:
            return None


chat_service = ChatService()
