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
import sys
from pathlib import Path
from typing import Callable, Optional

from common.paths import (
    BUSINESS_CONFIG_DIR,
    MYTEAM_ROOT,
    deliverables_dir,
    response_dir,
    workspace_dir,
)
from common.registry import get_spec, load_registry

# 决策类 kind 的 result 具体骨架（弱模型靠 response_schema 名字猜不出结构，须给样例，D11）。
_RESULT_SKELETON = {
    "team_config": '{"agents": ["<agent_id>", "..."]}',
    "task_plan": ('{"tasks": [{"id": "t1", "name": "任务名", "agent": "<agent_id>", '
                  '"task_type": "<task_type>", "description": "做什么", '
                  '"reviewer": "", "dependencies": []}]}'),
    "evaluate": '{"should_split": false, "reason": "理由", "sub_tasks": []}',
    "review": '{"passed": true, "feedback": "评审意见", "checklist": []}',
    "triage": '{"decision": "retry", "target_agent": "", "notes": "理由"}',
}


def _ensure_backend_importable() -> None:
    p = str(MYTEAM_ROOT / "backend")
    if p not in sys.path:
        sys.path.insert(0, p)


def _default_adapter():
    _ensure_backend_importable()
    from adapters.opencode.adapter import OpenCodeAdapter
    return OpenCodeAdapter()


def _default_request_factory(**kw):
    _ensure_backend_importable()
    from adapter.protocol import RunRequest
    return RunRequest(**kw)


def _load_agents_config() -> dict:
    path = BUSINESS_CONFIG_DIR / "agents_config.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


# ── 提示词渲染 ───────────────────────────────────────────────


def build_worker_prompt(req, resp_path: Path, deliv_dir: Path,
                        submit_script: Optional[Path] = None) -> str:
    """把 InteractionRequest 渲染为 worker 提示词。

    核心约束（消灭 F1）：结果**只能**通过 submit_result 写入 .response（契约本地校验），
    不要在聊天里返回 JSON。
    """
    submit_script = submit_script or (Path(__file__).resolve().parent / "submit_result.py")
    kind = req.kind
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

    if kind == "execute":
        rel = (req.input or {}).get("deliverable_path", f"{req.task_id}_deliverable.md")
        abs_dv = deliv_dir / rel
        task_type = (req.constraints or {}).get("task_type", "")
        spec = get_spec(task_type) if task_type else None
        lines.append(f"请完成任务并把交付物写入文件：{abs_dv}")
        if spec and spec.required_sections:
            lines.append(f"交付物须为 Markdown，包含 {spec.required_heading_level} 级标题章节：")
            for s in spec.required_sections:
                lines.append(f"  - {s}")
        if spec and spec.outcome_kind == "action":
            lines.append("这是动作型任务：必须真实执行动作并在交付物中记录【已发布URL】与【证据截图】路径。")
        outcome_hint = (
            '{"kind":"artifact","artifact":{"path":"%s","format":"markdown","title":"..."}}' % rel
        )
        result_hint = '"result": {"outcome": %s}' % outcome_hint
    else:
        lines.append("输入数据：")
        lines.append(json.dumps(req.input or {}, ensure_ascii=False))
        if kind == "task_plan":
            team = (req.input or {}).get("team") or []
            task_types = list(load_registry().keys())
            if team:
                lines.append(f"agent 字段只能从以下取：{', '.join(team)}")
            if task_types:
                lines.append(f"task_type 字段只能从以下取：{', '.join(task_types)}")
        result_hint = '"result": %s' % _RESULT_SKELETON.get(kind, "{ ... }")

    if req.retry_feedback:
        lines.append("")
        lines.append("【上一次未通过校验，请逐条修正】")
        for f in req.retry_feedback:
            lines.append(f"  ❌ {f}")

    lines += [
        "",
        "【提交结果（必须这样做）】",
        f"把结果 JSON 写入临时文件后，运行以下命令提交（会做契约校验并原子写回）：",
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


# ── Transport ────────────────────────────────────────────────


class AdapterTransport:
    """可调用对象，符合 AgentPort 的 Transport 协议：``__call__(ctx) -> None``。"""

    def __init__(self, adapter=None, *, agents_config: Optional[dict] = None,
                 rules_file: Optional[str] = None,
                 request_factory: Optional[Callable] = None,
                 prompt_builder: Callable = build_worker_prompt,
                 session_resolver: Optional[Callable[[str], Optional[str]]] = None):
        self._adapter = adapter
        self._agents_config = agents_config
        self.rules_file = rules_file
        self._request_factory = request_factory or _default_request_factory
        self.prompt_builder = prompt_builder
        self.session_resolver = session_resolver

    def _adapter_obj(self):
        if self._adapter is None:
            self._adapter = _default_adapter()
        return self._adapter

    def _config(self) -> dict:
        if self._agents_config is None:
            self._agents_config = _load_agents_config()
        return self._agents_config

    def _model(self, agent_id: str) -> str:
        return (self._config().get(agent_id, {}) or {}).get("model", "")

    def __call__(self, ctx) -> None:
        req = ctx.request
        ws = str(workspace_dir(req.agent_id))
        resp_path = response_dir(req.agent_id) / f"{req.interaction_id}.response"
        deliv_dir = deliverables_dir(req.project_id)
        prompt = self.prompt_builder(req, resp_path, deliv_dir)
        session_id = self.session_resolver(req.agent_id) if self.session_resolver else None

        run_req = self._request_factory(
            workspace=ws, message=prompt, model=self._model(req.agent_id),
            session_id=session_id, rules_file=self.rules_file,
            agent_id=req.agent_id, cancel_event=ctx.cancel_event,
        )

        for ev in self._adapter_obj().run(run_req):
            kind = getattr(ev.kind, "value", ev.kind)
            data = dict(getattr(ev, "data", {}) or {})
            ctx.emit(str(kind), data)
            if ctx.cancelled:
                break
