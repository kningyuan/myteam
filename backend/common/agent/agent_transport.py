#!/usr/bin/env python3
"""AgentPort 的真实 Transport（Phase 8 step 1）—— 驱动 CLI 适配器（默认 opencode）。

把一次 InteractionRequest 渲染成 worker 提示词，交给 `backend/adapters/opencode` 执行，
并把适配器产出的 `AgentEvent` 流转发到 `ctx.emit`（心跳/计量，D7/D12）。Agent 用
`submit_result` 把契约校验过的结果原子写回 `.response`，AgentPort 轮询采纳（D11/D12）。

适配器可注入（便于单测 / 换 claude）；真实适配器从 `backend/` 惰性导入，避免硬耦合。
本模块是 D2「机制进代码」的落点之一；live 跑通后再考虑上移 `backend/`。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from common.store.store import Store

from common.agent.agent_model import (
    resolve_agent_backend,
    resolve_agent_model,
)
from common.observability.audit_log import audit_enabled, clip_text
from common.paths import (
    BUSINESS_CONFIG_DIR,
    MYTEAM_ROOT,
    deliverables_dir,
    response_dir,
    workspace_dir,
)
from common.project.project_artifacts import is_code_project_task, task_project_dir
from common.prompt.prompt_composer import compose_execute_layers
from execution_harness.context import ExecuteHarnessContext
from execution_harness.facade import inject_for_execute, prepare_execute_harness
from common.gate.registry import load_registry

RULES_DIR = BUSINESS_CONFIG_DIR.parent / "rules"

_IDENTITY_FILES = ("AGENTS.md", "IDENTITY.md", "SOUL.md", "MEMORY.md")


def _resolve_harness_store(req) -> Optional["Store"]:
    """execute harness 可选绑定 Store（单测 / single_execute 用 context.store_path）。"""
    ctx = getattr(req, "context", None) or {}
    raw = ctx.get("store_path") if isinstance(ctx, dict) else None
    if not raw:
        return None
    from common.store.store import Store

    return Store(raw)


def parallel_execute_workspace(agent_id: str, req) -> Path:
    """L2 并行：同 agent 多任务时使用独立 cwd，避免 CLI 子进程争用同一 workspace。"""
    base = workspace_dir(agent_id)
    pid = getattr(req, "project_id", None) or ""
    tid = getattr(req, "task_id", None) or ""
    kind = getattr(req, "kind", None) or ""
    if kind != "execute" or not pid or not tid:
        return base
    iso = base / "_parallel" / pid / tid
    iso.mkdir(parents=True, exist_ok=True)
    for name in _IDENTITY_FILES:
        src = base / name
        dst = iso / name
        if not src.is_file() or dst.exists():
            continue
        try:
            os.symlink(src, dst)
        except OSError:
            shutil.copy2(src, dst)
    return iso


# 决策类 kind 的 result 具体骨架（弱模型靠 response_schema 名字猜不出结构，须给样例，D11）。
_RESULT_SKELETON = {
    "team_config": '{"agents": ["<agent_id>", "..."]}',
    "task_plan": ('{"tasks": [{"id": "t1", "name": "任务名", "agent": "<agent_id>", '
                  '"task_type": "<task_type>", "description": "做什么", '
                  '"reviewer": "", "dependencies": []}]}'),
    "evaluate": ('{"should_split": false, "reason": "为何拆/不拆", "sub_tasks": '
                 '[{"id": "s1", "name": "子任务名", "agent": "", "task_type": "", '
                 '"description": "做什么", "reviewer": "", "dependencies": []}]}'),
    "review": '{"passed": true, "feedback": "评审意见", "checklist": []}',
    "triage": (
        '{"decision": "retry|reassign|drop|abort|split", "target_agent": "", "notes": "理由", '
        '"sub_tasks": [{"id": "s1", "name": "子任务名", "agent": "", "task_type": "", '
        '"description": "做什么", "reviewer": "", "dependencies": []}]}'
        " — 参考 input.fail_reason / fail_detail 决策；任务过大无法一次完成时用 split 并给出 sub_tasks"
    ),
    "skill_review": (
        '{"action": "noop|patch|reference|create", "skill_id": "", "notes": "", "pending_content": ""}'
    ),
    "plan": (
        '{"approach": "总体思路/方法", "steps": ["步骤1", "步骤2", "..."], '
        '"risks": ["风险1", "..."], "confidence": 0.8}'
    ),
}


def _ensure_backend_importable() -> None:
    p = str(MYTEAM_ROOT / "backend")
    if p not in sys.path:
        sys.path.insert(0, p)


def _default_adapter(backend: str = "opencode"):
    _ensure_backend_importable()
    import adapter as _adapter  # noqa: F401  — side-effect CLI 注册 — side-effect registration

    from adapter.core.registry import registry

    adapter = registry.get(backend)
    if adapter is not None:
        return adapter
    fallback = registry.get("opencode")
    if fallback is not None:
        return fallback
    from adapter.opencode.adapter import OpenCodeAdapter

    return OpenCodeAdapter()


def _default_request_factory(**kw):
    _ensure_backend_importable()
    from adapter.core.protocol import RunRequest
    return RunRequest(**kw)


def _chinese_name(agent_id: str) -> str:
    """从 agents_registry.json 读取显示名，fallback 到 agent_id。"""
    try:
        from common.paths import BUSINESS_CONFIG_DIR
        import json
        path = BUSINESS_CONFIG_DIR / "agents_registry.json"
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            agents = raw.get("agents") if isinstance(raw, dict) else raw
            if isinstance(agents, dict):
                cfg = agents.get(agent_id)
                if isinstance(cfg, dict):
                    return str(cfg.get("name", "") or cfg.get("display_name", "") or agent_id)
    except Exception:
        pass
    return agent_id


def _build_rules_file(agent_id: str) -> Optional[str]:
    """项目 execute：universal + worker-template + AGENTS.md（D1 与 Hub 规则目录同源）。"""
    from common.gate.rules_merge import merge_rules_file

    ws = str(workspace_dir(agent_id))
    chinese_name = _chinese_name(agent_id)
    return merge_rules_file(
        agent_id,
        ws,
        RULES_DIR,
        profile="workflow_execute",
        chinese_name=chinese_name,
    )


def _load_agents_config() -> dict:
    path = BUSINESS_CONFIG_DIR / "agents_config.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _append_acceptance_criteria(lines: list, req, spec) -> None:
    criteria = (req.input or {}).get("acceptance_criteria") or (
        spec.acceptance_criteria if spec else []
    )
    if criteria:
        lines.append("【验收标准（交付物须满足，否则门禁不通过）】")
        for c in criteria:
            lines.append(f"  - {c}")


# ── 提示词渲染 ───────────────────────────────────────────────


def build_worker_prompt(req, resp_path: Path, deliv_dir: Path,
                        submit_script: Optional[Path] = None) -> str:
    """把 InteractionRequest 渲染为 worker 提示词。

    核心约束（消灭 F1）：结果**只能**通过 submit_result 写入 .response（契约本地校验），
    不要在聊天里返回 JSON。
    """
    submit_script = submit_script or (Path(__file__).resolve().parent / "submit_result.py")
    kind = req.kind

    if kind == "skill_review":
        from execution_harness.post.review import build_skill_review_prompt

        req_dict = req.model_dump() if hasattr(req, "model_dump") else dict(req)
        base = build_skill_review_prompt(req_dict)
        resp_path = response_dir(getattr(req, "agent_id", "") or "") / f"{req.interaction_id}.response"
        lines = [
            base,
            "",
            "【提交结果（必须这样做）】",
            f"  {sys.executable} {submit_script} --out {resp_path} --file <你的结果json文件>",
            "不要在聊天里直接返回 JSON。",
        ]
        return "\n".join(lines)

    lines = [
        f"你正在执行一次「{kind}」交互（interaction_id={req.interaction_id}）。",
        f"意图：{req.intent or '(见下方输入)'}",
        "",
    ]

    upstream = (req.context or {}).get("upstream") or []
    if upstream:
        lines.append("【上游已完成任务的摘要（仅供参考，勿照抄）】")
        for u in upstream:
            lines.append(f"- {u.get('task_id')}: {u.get('summary','')}（引用：{u.get('ref','')}）")
        lines.append("")

    plan = (req.context or {}).get("plan")
    if plan:
        lines.append(plan)
        lines.append("")

    # 路径 E：自我提升前置约束注入
    si_constraints = (req.context or {}).get("self_improve_constraints")
    if si_constraints:
        lines.append(si_constraints)
        lines.append("")

    if kind == "execute":
        rel = (req.input or {}).get("deliverable_path", f"{req.task_id}_deliverable.md")
        base = (req.input or {}).get("deliverable_base")
        abs_dv = (Path(base) / rel) if base else (deliv_dir / rel)
        task_type = (req.constraints or {}).get("task_type", "")
        template_id = str((req.constraints or {}).get("template_id") or "").strip() or None
        from common.gate.registry import resolve_format_spec
        spec = resolve_format_spec(task_type, template_id) if task_type else None
        from common.agent.agent_skills import append_skill_instructions

        append_skill_instructions(lines, req.agent_id, task_type=task_type or None)
        from common.agent.agent_mcp import append_mcp_instructions

        append_mcp_instructions(lines, req.agent_id)
        if spec and spec.template_id:
            lines.append(
                f"【交付模板】{spec.template_display_name or spec.template_id}（id={spec.template_id}）"
            )
            lines.append("须严格按模板章节与 Gate 规则交卷；章节标题与模板逐字一致。")
            lines.append("")
        profile = spec.delivery_profile if spec else "none"
        compose_execute_layers(lines, task_type, profile)
        hctx = ExecuteHarnessContext(
            lines=lines,
            project_id=req.project_id,
            task_id=req.task_id or "",
            task_type=task_type,
            agent_id=req.agent_id,
            intent=req.intent or "",
            store=_resolve_harness_store(req),
        )
        prepare_execute_harness(hctx)
        inject_for_execute(hctx)
        if spec and spec.outcome_kind == "code_project":
            proj = task_project_dir(req.project_id, req.task_id)
            lines.append("【交付物形态】代码工程目录（不是单篇说明文档）")
            lines.append(f"工程根目录（必须把所有产出写入此目录）：{proj}")
            if spec.structure:
                lines.append("【目录结构要求】")
                for row in spec.structure:
                    lines.append(f"  - {row}")
            if spec.sections:
                lines.append("【应包含的产出（每项须有对应实体文件）】")
                for sec in spec.sections:
                    if not isinstance(sec, dict):
                        continue
                    name = sec.get("name", "")
                    desc = sec.get("description", "")
                    ex = sec.get("example", "")
                    if name:
                        lines.append(f"  - {name}：{desc or '见示例'}")
                    if ex:
                        lines.append(f"    示例：{ex}")
            if spec.file_exists:
                lines.append("【门禁必选文件】")
                for f in spec.file_exists:
                    lines.append(f"  - {f}")
            lines.append(f"- submit_result 中 artifact.path 填 \"{req.task_id}/\"，artifact.format 填 \"code_project\"")
            _append_acceptance_criteria(lines, req, spec)
        elif spec and spec.outcome_kind == "action":
            lines.append(f"请完成任务并把交付物写入文件：{abs_dv}")
            lines.append("这是动作型任务：必须真实执行动作并在交付物中记录【已发布URL】与【证据截图】路径。")
            _append_acceptance_criteria(lines, req, spec)
        else:
            lines.append(f"请完成任务并把交付物写入文件：{abs_dv}")
            if abs_dv.is_file():
                lines.append(
                    f"（框架已预写章节骨架：{abs_dv} — 请直接编辑该文件补全各节正文，勿另建路径。）"
                )
            lines += [
                "",
                "【必须完成的两步（缺一不可）】",
                f"  1. 把完整交付物写入：{abs_dv}",
                "  2. 运行文末 submit_result 命令提交 JSON（仅聊天不算交卷）",
            ]
            intent = getattr(req, "intent", None) or (req.get("intent") if isinstance(req, dict) else "") or ""
            if "200字" in intent or "简短" in intent:
                lines.append(
                    "【短评任务】约200字即可；禁止全仓库扫描或长篇探索；"
                    "先写入交付物文件，再立即 submit_result。"
                )
            if spec:
                level = spec.required_heading_level or 2
                heading = "#" * level
                if spec.required_sections:
                    lines.append(
                        f"交付物须为 Markdown；下列章节标题必须是 {level} 级标题"
                        f"（行首 `{heading} 章节名`，不能只写在正文里提及）："
                    )
                    for s in spec.required_sections:
                        lines.append(f"  - {s}")
                if spec.sections:
                    lines.append("【章节标题逐字示例】")
                    for sec in spec.sections:
                        if not isinstance(sec, dict):
                            continue
                        name = sec.get("name", "")
                        if not name or not sec.get("required", True):
                            continue
                        lines.append(f"  - `{heading} {name}`")
                        desc = sec.get("description", "")
                        ex = sec.get("example", "")
                        if desc:
                            lines.append(f"    说明：{desc}")
                        if ex:
                            lines.append(f"    示例：{ex}")
                if spec.file_exists:
                    lines.append("【门禁必选文件（须与 deliverable 同目录）】")
                    for f in spec.file_exists:
                        lines.append(f"  - {f}")
                _append_acceptance_criteria(lines, req, spec)
        if spec and spec.outcome_kind == "code_project":
            outcome_hint = (
                '{"kind":"artifact","artifact":{"path":"%s/","format":"code_project","title":"..."}}'
                % req.task_id
            )
        else:
            outcome_hint = (
                '{"kind":"artifact","artifact":{"path":"%s","format":"markdown","title":"..."}}' % rel
            )
        result_hint = '"result": {"outcome": %s}' % outcome_hint
    elif kind == "review":
        rel = (req.input or {}).get("deliverable_path", f"{req.task_id}_deliverable.md")
        base = (req.input or {}).get("deliverable_base")
        abs_dv = (Path(base) / rel) if base else (deliv_dir / rel)
        criteria = (req.input or {}).get("acceptance_criteria") or []
        task_type = (req.constraints or {}).get("task_type", "")
        template_id = (req.input or {}).get("template_id") or (req.constraints or {}).get("template_id") or ""
        sections = (req.input or {}).get("template_sections") or []
        attach = (req.input or {}).get("file_exists") or []
        if template_id:
            lines.append(f"【交付模板】{template_id}")
        if is_code_project_task(task_type):
            proj = Path(base) if base else (deliv_dir / req.task_id)
            lines.append(f"请通读代码工程目录内全部相关文件：{proj}")
            lines.append("（脚本、README、测试用例/记录/报告、output/ 产出等均在此目录）")
        else:
            lines.append(f"请打开并通读交付物文件：{abs_dv}")
        if sections:
            lines.append("【逐章评审】对照模板每一章的内容质量（非仅标题是否存在）：")
            for sec in sections:
                if not isinstance(sec, dict):
                    continue
                name = sec.get("name", "")
                desc = sec.get("description", "")
                if name:
                    lines.append(f"  - ## {name}" + (f"：{desc}" if desc else ""))
        if attach:
            lines.append("【附件/图评审】须存在且与正文一致：")
            for f in attach:
                lines.append(f"  - {f}")
        if criteria:
            lines.append("【验收标准】逐条对照：")
            for c in criteria:
                lines.append(f"  - {c}")
        lines.append("【全文一致性】术语、范围、架构/流程描述前后须自洽，无矛盾。")
        lines.append("整体达标则 passed=true；否则 passed=false，feedback 按章节列出须修正之处。")
        result_hint = '"result": %s' % _RESULT_SKELETON["review"]
    elif kind == "plan":
        intent = getattr(req, "intent", None) or ""
        desc = ((req.input or {}).get("task") or {}).get("description", "")
        lines.append(f"任务意图：{intent}")
        if desc:
            lines.append(f"任务描述：{desc}")
        lines.append("")
        lines.append("【要求】请针对上述任务输出执行计划，包含以下字段：")
        lines.append("  - approach：总体思路/方法（10 字以上）")
        lines.append("  - steps：执行步骤列表（至少 1 个实质性步骤）")
        lines.append("  - risks：识别到的风险或不确定性（可选但建议 1+）")
        lines.append("  - confidence：对计划可行的信心（0..1，可选，默认 0.7）")
        lines.append("")
        lines.append("计划是执行前的思考，不是交付物。请确保思路合理、步骤可操作。")
        result_hint = '"result": %s' % _RESULT_SKELETON["plan"]
    else:
        lines.append("输入数据：")
        lines.append(json.dumps(req.input or {}, ensure_ascii=False))
        if kind in ("task_plan", "evaluate"):
            from common.agent.agent_registry import agent_task_type_map
            from common.gate.registry import task_type_label

            team = (req.input or {}).get("team") or []
            cap_map = agent_task_type_map()
            allowed: set[str] = set()
            if team:
                for aid in team:
                    for tt in cap_map.get(aid) or []:
                        allowed.add(tt)
            task_types = sorted(allowed) if allowed else list(load_registry().keys())
            if team:
                lines.append(f"agent 字段只能从以下取：{', '.join(team)}")
            if task_types:
                labels = [
                    f"{task_type_label(t)}（{t}）" for t in task_types
                ]
                lines.append(f"task_type 须与 agent 能力匹配，只能从以下取：{', '.join(labels)}")
        if kind == "evaluate":
            lines.append("如需拆分：每个子任务必须给出 agent 与 task_type（留空则继承父任务），"
                         "子任务依赖只能引用同组其它子任务 id；无需拆分则 should_split=false、sub_tasks 留空。")
        if kind == "triage":
            lines.append("若任务过大或失败因范围过宽：可用 decision=split 并给出 sub_tasks（格式同 evaluate）；"
                         "子任务依赖只能引用同组其它子任务 id。")
        result_hint = '"result": %s' % _RESULT_SKELETON.get(kind, "{ ... }")

    if req.retry_feedback:
        patch_hint = (req.constraints or {}).get("patch_hint", "")
        lines.append("")
        if patch_hint == "format_only":
            lines.append("【PATCH 修正 — 仅调整标题结构，保留正文】")
            for f in req.retry_feedback:
                if f.startswith("上一轮"):
                    lines.append(f"  📁 {f}")
                elif f.startswith("【"):
                    lines.append(f"  {f}")
                else:
                    lines.append(f"  ❌ {f}")
            lines.append("")
            lines.append("【指示】交付物已存在，仅修正标题层级与章节名使其通过门禁；")
            lines.append("禁止重读仓库、禁止重写正文、禁止重新调研。")
        else:
            # 结构化重试反馈：可能含 【】 分类块、→ 指引行、❌ 失败详情
            has_classified = any(f.startswith("【失败根因分类") for f in req.retry_feedback)
            if has_classified:
                lines.append("【上一轮门禁失败 — 按类别修复】")
                in_detail = False
                for f in req.retry_feedback:
                    if f.startswith("【失败详情】"):
                        lines.append("")
                        lines.append("  ── 具体失败条目 ──")
                        in_detail = True
                        continue
                    if f.startswith("【失败根因分类"):
                        lines.append(f"  {f}")
                    elif in_detail:
                        lines.append(f"  ❌ {f}")
                    elif f.strip().startswith("→"):
                        lines.append(f"    🔧 {f.strip()}")
                    elif f.strip().startswith("┃") or not f.strip():
                        lines.append(f"  {f}")
                    else:
                        lines.append(f"  {f}")
            else:
                lines.append("【PATCH 修正 — 针对以下问题做定点修改】")
                for f in req.retry_feedback:
                    lines.append(f"  ❌ {f}")
            lines.append("")
            dv_path = (req.input or {}).get("deliverable_path", "")
            if dv_path:
                lines.append(f"交付物文件：{dv_path}（请直接编辑此文件，不要重写）")

    # 通用工程师思维循环 — 先想再做，自检后再提交
    from execution_harness.pre.engineer_loop import ENGINEER_LOOP_BLOCK
    lines.append("")
    lines.append(ENGINEER_LOOP_BLOCK.strip())
    lines.append("")

    lines += [
        "",
        "【提交结果（必须这样做）】",
        "把结果 JSON 写入临时文件后，运行以下命令提交（会做契约校验并原子写回）：",
        f"  {sys.executable} {submit_script} --out {resp_path} --file <你的结果json文件>",
        "结果 JSON 必须形如：",
        "{",
        f'  "interaction_id": "{req.interaction_id}",',
        f'  "kind": "{kind}", "status": "ok",',
        ('  "quality": {"score": 0.x, "known_gaps": [], "notes": "自评"},'
         if kind in ("execute", "review") else "  "),
        f"  {result_hint},",
        '  "notes": "100 字内的成果摘要（将作为下游上下文）"',
        "}",
        "不要在聊天里直接返回 JSON；聊天内容会被忽略。只有写入 .response 的合法结果才被采纳。",
    ]
    return "\n".join(lines)


# ── Gate retry session ───────────────────────────────────────


def _parse_execute_attempt(interaction_id: str) -> int:
    try:
        return int(interaction_id.rsplit(":", 1)[-1])
    except ValueError:
        return 1


def lookup_interaction_session(store: "Store", interaction_id: str) -> Optional[str]:
    """从 run_event 中取该 interaction 最后一次 session 事件里的 session_id。"""
    sid = None
    for ev in store.list_run_events(interaction_id):
        if ev.get("kind") != "session":
            continue
        payload = ev.get("payload") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
        if isinstance(payload, dict):
            sid = payload.get("session_id") or sid
    return sid


def resolve_gate_retry_session(store: "Store", req) -> Optional[str]:
    """execute 门禁重试（attempt>1）时复用上一轮 CLI session。"""
    if getattr(req, "kind", None) != "execute":
        return None
    attempt = _parse_execute_attempt(req.interaction_id)
    if attempt <= 1:
        return None
    inp = req.input or {}
    ctx = req.context or {}
    sid = inp.get("session_id") or ctx.get("session_id")
    if sid:
        return sid
    prev_iid = f"{req.project_id}:{req.task_id}:execute:{attempt - 1}"
    return lookup_interaction_session(store, prev_iid)


def make_gate_session_resolver(store: "Store"):
    """供 run_kernel 注入 AdapterTransport.session_resolver。"""

    def resolver(agent_id: str, req) -> Optional[str]:
        return resolve_gate_retry_session(store, req)

    return resolver


# ── Transport ────────────────────────────────────────────────


class AdapterTransport:
    """可调用对象，符合 AgentPort 的 Transport 协议：``__call__(ctx) -> None``。"""

    def __init__(self, adapter=None, *, backend: str = "opencode",
                 agents_config: Optional[dict] = None,
                 rules_file: Optional[str] = None,
                 request_factory: Optional[Callable] = None,
                 prompt_builder: Callable = build_worker_prompt,
                 session_resolver: Optional[Callable[..., Optional[str]]] = None):
        self._adapter = adapter
        self._backend = backend
        self._adapter_cache: dict[str, object] = {}
        self._agents_config = agents_config
        self.rules_file = rules_file
        self._request_factory = request_factory or _default_request_factory
        self.prompt_builder = prompt_builder
        self.session_resolver = session_resolver

    def _backend_for(self, agent_id: str) -> str:
        cfg = self._config()
        explicit = (cfg.get(agent_id, {}) or {}).get("backend", "").strip()
        if explicit:
            return explicit
        if self._agents_config is not None:
            return self._backend
        return resolve_agent_backend(agent_id, config=cfg)

    def _adapter_obj(self, agent_id: str):
        if self._adapter is not None:
            return self._adapter
        backend = self._backend_for(agent_id)
        if backend not in self._adapter_cache:
            self._adapter_cache[backend] = _default_adapter(backend)
        return self._adapter_cache[backend]

    def _config(self) -> dict:
        # 未注入固定配置时每次从磁盘读取，便于运行中改模型/backend 后下一交互生效。
        if self._agents_config is not None:
            return self._agents_config
        return _load_agents_config()

    def _model(self, agent_id: str) -> str:
        cfg = self._config()
        explicit = (cfg.get(agent_id, {}) or {}).get("model", "").strip()
        if explicit:
            return explicit
        return resolve_agent_model(agent_id, config=cfg)

    def __call__(self, ctx) -> None:
        req = ctx.request
        ws = str(parallel_execute_workspace(req.agent_id, req))
        resp_path = response_dir(req.agent_id) / f"{req.interaction_id}.response"
        if (req.input or {}).get("deliverable_base"):
            deliv_dir = Path((req.input or {})["deliverable_base"])
        else:
            deliv_dir = deliverables_dir(req.project_id)
        prompt = self.prompt_builder(req, resp_path, deliv_dir)
        if audit_enabled():
            ctx.emit("prompt_sent", {
                "agent_id": req.agent_id,
                "model": self._model(req.agent_id),
                "prompt_len": len(prompt),
                "prompt": clip_text(prompt),
            })
        session_id = None
        if self.session_resolver:
            try:
                session_id = self.session_resolver(req.agent_id, req)
            except TypeError:
                session_id = self.session_resolver(req.agent_id)
        attempt = _parse_execute_attempt(req.interaction_id)
        if session_id and attempt > 1:
            ctx.emit("gate_retry_session", {
                "session_id": session_id,
                "attempt": attempt,
                "task_id": req.task_id,
                "project_id": req.project_id,
            })
        if not session_id:
            session_id = (req.input or {}).get("session_id")
        rules_file = self.rules_file or _build_rules_file(req.agent_id)

        run_req = self._request_factory(
            workspace=ws, message=prompt, model=self._model(req.agent_id),
            session_id=session_id, rules_file=rules_file,
            agent_id=req.agent_id, cancel_event=ctx.cancel_event,
            extra={"dispatch_token": req.interaction_id},
        )

        for ev in self._adapter_obj(req.agent_id).run(run_req):
            kind = getattr(ev.kind, "value", ev.kind)
            data = dict(getattr(ev, "data", {}) or {})
            ctx.emit(str(kind), data)
            if ctx.cancelled:
                break
