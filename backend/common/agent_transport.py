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
import tempfile
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from common.store import Store

from common.agent_model import (
    resolve_agent_backend,
    resolve_agent_model,
)
from common.audit_log import audit_enabled, clip_text
from common.paths import (
    BUSINESS_CONFIG_DIR,
    MYTEAM_ROOT,
    deliverables_dir,
    response_dir,
    workspace_dir,
)
from common.project_artifacts import is_code_project_task, task_project_dir
from common.prompt_composer import compose_execute_layers
from common.experience import append_experience_hints
from common.registry import get_spec, load_registry

RULES_DIR = BUSINESS_CONFIG_DIR.parent / "rules"

_IDENTITY_FILES = ("AGENTS.md", "IDENTITY.md", "SOUL.md", "MEMORY.md")


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

_AGENT_DISPLAY_NAMES = {
    "main": "项目协调专家",
    "product": "产品经理",
    "developer": "开发工程师",
    "research": "研究员",
    "content": "内容创作者",
}

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
        '{"decision": "retry|reassign|drop", "target_agent": "", "notes": "理由"}'
        " — 参考 input.fail_reason / fail_detail 决策，勿忽略具体失败原因"
    ),
}


def _ensure_backend_importable() -> None:
    p = str(MYTEAM_ROOT / "backend")
    if p not in sys.path:
        sys.path.insert(0, p)


def _default_adapter(backend: str = "opencode"):
    _ensure_backend_importable()
    if backend == "claude":
        from adapters.claude import ClaudeCodeAdapter
        return ClaudeCodeAdapter()
    from adapters.opencode.adapter import OpenCodeAdapter
    return OpenCodeAdapter()


def _default_request_factory(**kw):
    _ensure_backend_importable()
    from adapter.protocol import RunRequest
    return RunRequest(**kw)


def _build_rules_file(agent_id: str) -> Optional[str]:
    """合并 universal-rules + AGENTS.md，供内核 execute 与 Hub 聊天同源（D1）。"""
    ws = str(workspace_dir(agent_id))
    universal = RULES_DIR / "universal-rules.md"
    agents_md = Path(ws) / "AGENTS.md"
    try:
        fd, temp_path = tempfile.mkstemp(
            suffix=".md", prefix=f"rules-{agent_id}-", dir="/tmp",
        )
        chinese_name = _AGENT_DISPLAY_NAMES.get(agent_id, agent_id)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"# {chinese_name} - 完整规则\n\n")
            if universal.exists():
                f.write(universal.read_text(encoding="utf-8"))
                f.write("\n\n---\n\n")
            for name in ["brainstorming-guide.md", "worker-template.md"]:
                fp = RULES_DIR / name
                if agent_id != "main" and fp.exists():
                    f.write(fp.read_text(encoding="utf-8"))
                    f.write("\n\n---\n\n")
            if agents_md.exists():
                f.write(agents_md.read_text(encoding="utf-8"))
        return temp_path
    except Exception:
        return None


def _load_agents_config() -> dict:
    path = BUSINESS_CONFIG_DIR / "agents_config.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _task_type_skill_path(task_type: str) -> Optional[Path]:
    """business/skills/<task_type>/SKILL.md，若存在则注入 execute 提示词。"""
    if not task_type:
        return None
    p = MYTEAM_ROOT / "business" / "skills" / task_type / "SKILL.md"
    return p if p.is_file() else None


def _append_acceptance_criteria(lines: list[str], req, spec) -> None:
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
        base = (req.input or {}).get("deliverable_base")
        abs_dv = (Path(base) / rel) if base else (deliv_dir / rel)
        task_type = (req.constraints or {}).get("task_type", "")
        spec = get_spec(task_type) if task_type else None
        skill_path = _task_type_skill_path(task_type) if task_type else None
        if skill_path:
            lines.append(f"【任务类型执行指引】请先阅读并按其中流程执行：{skill_path}")
            lines.append("")
        profile = spec.delivery_profile if spec else "none"
        compose_execute_layers(lines, task_type, profile)
        append_experience_hints(lines, req.project_id, task_type)
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
                f"  2. 运行文末 submit_result 命令提交 JSON（仅聊天不算交卷）",
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
        if is_code_project_task(task_type):
            proj = Path(base) if base else (deliv_dir / req.task_id)
            lines.append(f"请通读代码工程目录内全部相关文件：{proj}")
            lines.append("（脚本、README、测试用例/记录/报告、output/ 产出等均在此目录）")
        else:
            lines.append(f"请打开并通读交付物文件：{abs_dv}")
        if criteria:
            lines.append("逐条对照以下验收标准评审：")
            for c in criteria:
                lines.append(f"  - {c}")
        lines.append("整体达标则 passed=true；否则 passed=false，并在 feedback 写明须修正之处。")
        result_hint = '"result": %s' % _RESULT_SKELETON["review"]
    else:
        lines.append("输入数据：")
        lines.append(json.dumps(req.input or {}, ensure_ascii=False))
        if kind in ("task_plan", "evaluate"):
            from common.agent_registry import agent_task_type_map
            from common.registry import TASK_TYPE_DISPLAY_NAMES

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
                    f"{TASK_TYPE_DISPLAY_NAMES.get(t, t)}（{t}）" for t in task_types
                ]
                lines.append(f"task_type 须与 agent 能力匹配，只能从以下取：{', '.join(labels)}")
        if kind == "evaluate":
            lines.append("如需拆分：每个子任务必须给出 agent 与 task_type（留空则继承父任务），"
                         "子任务依赖只能引用同组其它子任务 id；无需拆分则 should_split=false、sub_tasks 留空。")
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
        )

        for ev in self._adapter_obj(req.agent_id).run(run_req):
            kind = getattr(ev.kind, "value", ev.kind)
            data = dict(getattr(ev, "data", {}) or {})
            ctx.emit(str(kind), data)
            if ctx.cancelled:
                break
