#!/usr/bin/env python3
"""Workflow loop 运行时 — 条件循环编排（R-Loop）。

机制在此；循环定义在 business/workflows/*.yaml 的 loops 段。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from common.project_artifacts import artifact_rel_path, task_deliverable_base

if TYPE_CHECKING:
    from common.process_types import TaskExecuteResult, TaskOutcome
    from common.store import Store

_TERMINAL_OK = frozenset({"completed", "needs_review"})
_TERMINAL_BAD = frozenset({"failed", "blocked"})


@dataclass
class AssessSpec:
    ref: str
    inputs: list[dict] = field(default_factory=list)


@dataclass
class TransitionRule:
    when: str = ""
    task: str = ""
    marker: str = ""
    action: str = ""
    outcome: str = ""
    next_body: str = ""


@dataclass
class TransitionResult:
    action: str
    outcome: str | None = None
    next_body: str | None = None
    matched_rule: int | None = None
    passed: bool = False


@dataclass
class LoopRoundState:
    round: int = 0
    body_key: str = "default"
    next_body_key: str | None = None
    rounds_used: int = 0


@dataclass
class RunLoopDeps:
    execute_task: Callable[[str, dict], "TaskExecuteResult"]
    persist_tasks: Callable[[str, list[dict]], None]
    append_run_event: Callable[[str, str, dict], None]
    update_task_meta: Callable[..., None]
    set_task_status: Callable[[str, str, str], None]
    store: "Store"
    on_loop_round_done: Optional[Callable[..., None]] = None
    needs_review_blocks: bool = False
    expand_ready: Optional[
        Callable[..., bool]
    ] = None


@dataclass
class LoopSpec:
    id: str
    max_rounds: int = 5
    min_rounds: int = 1
    default_body: str = "default"
    body: list[dict] = field(default_factory=list)
    until: list[dict] = field(default_factory=list)
    bodies: dict[str, list[dict]] = field(default_factory=dict)
    assess: Optional[AssessSpec] = None
    transition: list[TransitionRule] = field(default_factory=list)
    fallback_until: list[dict] = field(default_factory=list)
    on_pass: str = "complete"
    on_exhaust: str = "needs_review"
    description: str = ""
    is_v2: bool = False

    def body_for(self, branch: str | None = None) -> list[dict]:
        """Return body template for branch key (v2) or v1 body."""
        if self.bodies:
            key = (branch or self.default_body or "default").strip()
            if key not in self.bodies:
                raise KeyError(
                    f"loop「{self.id}」body 键「{key}」不存在；"
                    f"可用：{', '.join(sorted(self.bodies))}",
                )
            return self.bodies[key]
        return self.body

    def normalized_bodies(self) -> dict[str, list[dict]]:
        """All body branches keyed by name (v1 → single default)."""
        if self.bodies:
            return self.bodies
        if self.body:
            return {"default": self.body}
        return {}


def iter_loop_body_tasks(spec: LoopSpec):
    """Yield all body template tasks (every branch for v2)."""
    if spec.bodies:
        for tasks in spec.bodies.values():
            for t in tasks:
                yield t
    else:
        for t in spec.body:
            yield t


def _parse_dict_list(raw, *, field_name: str) -> list[dict]:
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} 必须是数组")
    return [dict(x) for x in raw if isinstance(x, dict)]


def _parse_assess(raw, *, loop_id: str) -> Optional[AssessSpec]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"loop「{loop_id}」assess 必须是对象")
    ref = str(raw.get("ref") or "").strip()
    if not ref:
        raise ValueError(f"loop「{loop_id}」assess.ref 不能为空")
    inputs = _parse_dict_list(raw.get("inputs") or [], field_name=f"loop「{loop_id}」assess.inputs")
    return AssessSpec(ref=ref, inputs=inputs)


def _parse_transition(raw, *, loop_id: str) -> list[TransitionRule]:
    items = _parse_dict_list(raw or [], field_name=f"loop「{loop_id}」transition")
    out: list[TransitionRule] = []
    for item in items:
        out.append(TransitionRule(
            when=str(item.get("when") or "").strip(),
            task=str(item.get("task") or "").strip(),
            marker=str(item.get("marker") or ""),
            action=str(item.get("action") or "").strip(),
            outcome=str(item.get("outcome") or "").strip(),
            next_body=str(item.get("next_body") or "").strip(),
        ))
    return out


def _parse_bodies(raw, *, loop_id: str) -> dict[str, list[dict]]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"loop「{loop_id}」bodies 须为非空对象")
    bodies: dict[str, list[dict]] = {}
    for key, tasks in raw.items():
        k = str(key or "").strip()
        if not k:
            raise ValueError(f"loop「{loop_id}」bodies 键不能为空")
        tpl = _parse_dict_list(tasks, field_name=f"loop「{loop_id}」bodies.{k}")
        if not tpl:
            raise ValueError(f"loop「{loop_id}」bodies.{k} 须为非空数组")
        bodies[k] = tpl
    return bodies


def parse_loop_specs(raw_loops) -> list[LoopSpec]:
    """从 workflow YAML loops 段解析 LoopSpec 列表。"""
    if not raw_loops:
        return []
    if not isinstance(raw_loops, list):
        raise ValueError("loops 必须是数组")
    out: list[LoopSpec] = []
    for item in raw_loops:
        if not isinstance(item, dict):
            raise ValueError("loops[] 每项必须是对象")
        lid = str(item.get("id") or "").strip()
        if not lid:
            raise ValueError("loops[].id 不能为空")
        has_v2 = bool(item.get("bodies"))
        has_v1 = bool(item.get("body"))
        if has_v2 and has_v1:
            raise ValueError(f"loop「{lid}」bodies 与 body 互斥")
        try:
            max_rounds = int(item.get("max_rounds", 5))
        except (TypeError, ValueError) as e:
            raise ValueError(f"loop「{lid}」max_rounds 无效") from e
        if max_rounds < 1:
            raise ValueError(f"loop「{lid}」max_rounds 须 ≥ 1")
        try:
            min_rounds = int(item.get("min_rounds", 1))
        except (TypeError, ValueError) as e:
            raise ValueError(f"loop「{lid}」min_rounds 无效") from e
        if min_rounds < 1:
            raise ValueError(f"loop「{lid}」min_rounds 须 ≥ 1")
        default_body = str(item.get("default_body") or "default").strip() or "default"

        if has_v2:
            bodies = _parse_bodies(item["bodies"], loop_id=lid)
            if default_body not in bodies:
                raise ValueError(
                    f"loop「{lid}」default_body「{default_body}」不在 bodies 中",
                )
            transition = _parse_transition(item.get("transition"), loop_id=lid)
            assess = _parse_assess(item.get("assess"), loop_id=lid)
            fallback = _parse_dict_list(
                item.get("fallback_until") or item.get("until") or [],
                field_name=f"loop「{lid}」fallback_until",
            )
            out.append(LoopSpec(
                id=lid,
                max_rounds=max_rounds,
                min_rounds=min_rounds,
                default_body=default_body,
                body=[],
                until=[],
                bodies=bodies,
                assess=assess,
                transition=transition,
                fallback_until=fallback,
                on_pass=str(item.get("on_pass") or "complete").strip() or "complete",
                on_exhaust=str(item.get("on_exhaust") or "needs_review").strip() or "needs_review",
                description=str(item.get("description") or "").strip(),
                is_v2=True,
            ))
            continue

        body = item.get("body")
        if not isinstance(body, list) or not body:
            raise ValueError(f"loop「{lid}」须定义非空 body")
        until = item.get("until")
        if not isinstance(until, list) or not until:
            raise ValueError(f"loop「{lid}」须定义非空 until")
        body_tpl = [dict(b) for b in body if isinstance(b, dict)]
        until_tpl = [dict(u) for u in until if isinstance(u, dict)]
        out.append(LoopSpec(
            id=lid,
            max_rounds=max_rounds,
            min_rounds=min_rounds,
            default_body=default_body,
            body=body_tpl,
            until=until_tpl,
            bodies={"default": body_tpl},
            assess=None,
            transition=[],
            fallback_until=until_tpl,
            on_pass=str(item.get("on_pass") or "complete").strip() or "complete",
            on_exhaust=str(item.get("on_exhaust") or "needs_review").strip() or "needs_review",
            description=str(item.get("description") or "").strip(),
            is_v2=False,
        ))
    return out


def loop_body_task_id(loop_id: str, round_num: int, body_id: str) -> str:
    return f"{loop_id}-r{round_num}-{body_id}"


def _inject_loop_vars(text: str, *, loop_id: str, round_num: int, max_rounds: int) -> str:
    prev_round = max(0, round_num - 1)
    prev_work_task_id = loop_body_task_id(loop_id, prev_round, "work") if prev_round else ""
    prev_review_task_id = loop_body_task_id(loop_id, prev_round, "review") if prev_round else ""
    work_task_id = loop_body_task_id(loop_id, round_num, "work")
    review_task_id = loop_body_task_id(loop_id, round_num, "review")
    return (
        (text or "")
        .replace("{round}", str(round_num))
        .replace("{max_rounds}", str(max_rounds))
        .replace("{loop_id}", loop_id)
        .replace("{prev_round}", str(prev_round))
        .replace("{prev_work_task_id}", prev_work_task_id)
        .replace("{prev_review_task_id}", prev_review_task_id)
        .replace("{work_task_id}", work_task_id)
        .replace("{review_task_id}", review_task_id)
    )


def seed_patch_baseline(project_id: str, prev_task_id: str, cur_task_id: str) -> bool:
    """复制上一轮 work 交付物为本轮 PATCH 初稿（定点改稿，非重写）。"""
    from common.paths import PROJECTS_DIR

    ddir = PROJECTS_DIR / project_id / "deliverables"
    prev = ddir / f"{prev_task_id}_deliverable.md"
    cur = ddir / f"{cur_task_id}_deliverable.md"
    if not prev.is_file():
        return False
    cur.parent.mkdir(parents=True, exist_ok=True)
    cur.write_text(prev.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    return True


def build_patch_goal_prefix(project_id: str, round_num: int, loop_id: str) -> str:
    """第 2+ 轮 work 任务前缀：强调定点 PATCH + 引用群讨论对齐清单。"""
    if round_num <= 1:
        return ""
    from common.store import Store

    prev_work = loop_body_task_id(loop_id, round_num - 1, "work")
    cur_work = loop_body_task_id(loop_id, round_num, "work")
    lines = [
        "【改稿模式：定点 PATCH — 禁止全文重写】",
        f"- 基线：deliverables/{prev_work}_deliverable.md",
        f"- 本轮初稿已复制为：deliverables/{cur_work}_deliverable.md",
        "- **仅修改**群讨论「定点改稿清单」中列出的 ### 小节或段落",
        "- 清单外的章节保持原文不变（措辞、结构、顺序均勿动）",
        "- 架构图仅当清单明确要求时才改 drawio/png",
        "",
    ]
    store = Store()
    try:
        meta = (store.get_project(project_id) or {}).get("meta") or {}
        disc = meta.get("last_loop_discussion")
        patch = meta.get("last_loop_patch_list")
        if patch:
            lines.append("【定点改稿清单（已与 main 对齐）】")
            lines.append(patch)
            lines.append("")
        if disc:
            lines.append("【群讨论对齐摘要】")
            lines.append(disc)
            lines.append("")
        disc_file = meta.get("last_loop_discussion_file")
        if disc_file:
            lines.append(f"（讨论全文：deliverables/{disc_file}）")
            lines.append("")
    finally:
        store.close()
    return "\n".join(lines) + "\n"


def resolve_assess_task_id(
    spec: LoopSpec,
    round_num: int,
    body_key: str | None = None,
    *,
    body_ref: str | None = None,
) -> str:
    """assess.ref 或显式 body_ref → 本轮绝对 task id。"""
    ref = (body_ref or (spec.assess.ref if spec.assess else "") or "review").strip() or "review"
    return loop_body_task_id(spec.id, round_num, ref)


def _task_type_for_body_ref(spec: LoopSpec, body_key: str, body_ref: str) -> str:
    for tpl in spec.body_for(body_key):
        if str(tpl.get("id") or "").strip() == body_ref:
            return str(tpl.get("task_type") or "")
    return ""


def resolve_assess_inputs(
    spec: LoopSpec,
    project_id: str,
    round_num: int,
    body_key: str,
    store: "Store",
    goal_text: str,
) -> str:
    """解析 assess.inputs，生成为 assess 任务注入的 description 片段。"""
    if not spec.assess or not spec.assess.inputs:
        return ""
    snippets: list[str] = []
    for raw in spec.assess.inputs:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or "").strip()
        optional = bool(raw.get("optional"))
        if kind == "goal":
            if goal_text.strip():
                snippets.append(f"【项目目标】\n{goal_text.strip()}")
        elif kind == "phase.deliverable":
            phase = str(raw.get("phase") or "").strip()
            if not phase:
                continue
            tid = loop_body_task_id(spec.id, round_num, phase)
            tt = _task_type_for_body_ref(spec, body_key, phase)
            text = _read_deliverable(project_id, tid, tt)
            if text.strip():
                snippets.append(f"【{phase} 交付物 · {tid}】\n{text.strip()[:8000]}")
            elif not optional:
                snippets.append(f"【{phase} 交付物】（尚未生成，task_id={tid}）")
        elif kind == "ops_log":
            table = str(raw.get("table") or "publish_log").strip() or "publish_log"
            meta = (store.get_project(project_id) or {}).get("meta") or {}
            meta_key = f"ops_log_{table}"
            log_text = str(meta.get(meta_key) or meta.get("last_ops_log") or "").strip()
            if not log_text and table == "publish_log":
                try:
                    rows = store.list_publish_logs(project_id, limit=10)
                except Exception:
                    rows = []
                if rows:
                    lines = []
                    for row in rows:
                        platform = row.get("platform") or "?"
                        deliverable = row.get("deliverable") or row.get("url") or ""
                        lines.append(f"- {platform}: {deliverable}")
                    log_text = "\n".join(lines)
            if log_text:
                snippets.append(f"【运营日志 · {table}】\n{log_text[:4000]}")
    return "\n\n".join(snippets)


def _round_num_from_loop_task_id(loop_id: str, task_id: str) -> int | None:
    prefix = f"{loop_id}-r"
    if not task_id.startswith(prefix):
        return None
    rest = task_id[len(prefix):]
    digits = ""
    for ch in rest:
        if ch.isdigit():
            digits += ch
        else:
            break
    return int(digits) if digits else None


def reconstruct_loop_state(
    store: "Store",
    project_id: str,
    loop_id: str,
    spec: LoopSpec,
) -> LoopRoundState | None:
    """从 run_event + 已有 round task 恢复 LoopRoundState；已完成 loop 返回 None。"""
    scope = f"{project_id}:loop:{loop_id}"
    events = store.list_run_events(scope)
    if any(e.get("kind") == "loop_finished" for e in events):
        return None

    last_round_done = 0
    body_key = spec.default_body
    pending_next_body: str | None = None

    for e in events:
        kind = e.get("kind")
        payload = e.get("payload") or {}
        if kind == "loop_round_done":
            last_round_done = max(last_round_done, int(payload.get("round") or 0))
            body_key = str(payload.get("body_key") or body_key)
        elif kind == "loop_round_assess":
            body_key = str(payload.get("body_key") or body_key)
        elif kind == "loop_transition":
            pending_next_body = str(payload.get("to_body") or "").strip() or None

    round_tasks: dict[int, list[dict]] = {}
    for row in store.list_tasks(project_id):
        tid = str(row.get("task_id") or "")
        rn = _round_num_from_loop_task_id(loop_id, tid)
        if rn is not None:
            round_tasks.setdefault(rn, []).append(row)

    incomplete_round: int | None = None
    for rn in sorted(round_tasks):
        statuses = {str(t.get("status") or "") for t in round_tasks[rn]}
        if statuses - _TERMINAL_OK - _TERMINAL_BAD - frozenset({"cancelled"}):
            incomplete_round = rn
            break

    if last_round_done == 0 and incomplete_round is None:
        return None

    if incomplete_round is not None:
        return LoopRoundState(
            round=incomplete_round,
            body_key=body_key,
            next_body_key=None,
            rounds_used=max(0, incomplete_round - 1),
        )

    if last_round_done >= spec.max_rounds:
        return None

    resume_body = pending_next_body or body_key
    return LoopRoundState(
        round=last_round_done + 1,
        body_key=resume_body,
        next_body_key=None,
        rounds_used=last_round_done,
    )


def resolve_work_task_id(
    spec: LoopSpec,
    round_num: int,
    body_key: str | None = None,
) -> str:
    """work 步骤 id；若无 work 则取 body 首步。"""
    body_tpl = spec.body_for(body_key)
    for tpl in body_tpl:
        bid = str(tpl.get("id") or "").strip()
        if bid == "work":
            return loop_body_task_id(spec.id, round_num, "work")
    first = str(body_tpl[0].get("id") or "").strip() if body_tpl else "work"
    return loop_body_task_id(spec.id, round_num, first or "work")


def _marker_implies_pass(marker: str) -> bool:
    m = (marker or "").strip().upper()
    return m in ("REVIEW: PASS", "ITERATION: PASS")


def evaluate_transition(
    spec: LoopSpec,
    *,
    round_num: int,
    body_key: str,
    project_id: str,
    round_outcomes: dict[str, "TaskOutcome"],
    body_task_types: dict[str, str],
    store: "Store",
) -> TransitionResult:
    """有序匹配 transition[]；无规则或未命中时回退 fallback_until / until OR 语义。"""
    for idx, rule in enumerate(spec.transition):
        when = (rule.when or "").strip()
        if when == "deliverable_marker":
            body_ref = (rule.task or "").strip()
            if not body_ref or not rule.marker:
                continue
            tid = loop_body_task_id(spec.id, round_num, body_ref)
            tt = body_task_types.get(tid, "")
            text = _read_deliverable(project_id, tid, tt)
            if rule.marker in text:
                action = (rule.action or "exit").strip() or "exit"
                outcome = (rule.outcome or "").strip() or None
                passed = _marker_implies_pass(rule.marker)
                if action == "exit" and not outcome:
                    outcome = spec.on_pass if passed else spec.on_exhaust
                return TransitionResult(
                    action=action,
                    outcome=outcome,
                    next_body=(rule.next_body or "").strip() or None,
                    matched_rule=idx,
                    passed=passed,
                )
        elif when == "gate_passed":
            body_ref = (rule.task or "").strip()
            if not body_ref:
                continue
            tid = loop_body_task_id(spec.id, round_num, body_ref)
            o = round_outcomes.get(tid)
            if o and o.status == "completed":
                action = (rule.action or "exit").strip() or "exit"
                outcome = (rule.outcome or spec.on_pass).strip() or spec.on_pass
                return TransitionResult(
                    action=action,
                    outcome=outcome,
                    next_body=(rule.next_body or "").strip() or None,
                    matched_rule=idx,
                    passed=True,
                )
        elif when == "task_status":
            body_ref = (rule.task or "").strip()
            want = (rule.status or "").strip()
            if not body_ref or not want:
                continue
            tid = loop_body_task_id(spec.id, round_num, body_ref)
            o = round_outcomes.get(tid)
            if o and o.status == want:
                action = (rule.action or "exit").strip() or "exit"
                return TransitionResult(
                    action=action,
                    outcome=(rule.outcome or "").strip() or None,
                    next_body=(rule.next_body or "").strip() or None,
                    matched_rule=idx,
                    passed=want in _TERMINAL_OK,
                )
        elif when == "exhausted" and round_num >= spec.max_rounds:
            outcome = (rule.outcome or spec.on_exhaust).strip() or spec.on_exhaust
            return TransitionResult(
                action=(rule.action or "exit").strip() or "exit",
                outcome=outcome,
                next_body=None,
                matched_rule=idx,
                passed=False,
            )

    until_conds = spec.until if spec.until else spec.fallback_until
    if until_conds:
        branch_spec = LoopSpec(
            id=spec.id,
            max_rounds=spec.max_rounds,
            body=spec.body_for(body_key),
            until=until_conds,
        )
        if evaluate_until(
            branch_spec, round_num, round_outcomes, store, project_id, body_task_types,
        ):
            return TransitionResult(
                action="exit",
                outcome=spec.on_pass,
                next_body=None,
                matched_rule=None,
                passed=True,
            )

    if round_num >= spec.max_rounds:
        return TransitionResult(
            action="exit",
            outcome=spec.on_exhaust,
            next_body=None,
            matched_rule=None,
            passed=False,
        )

    return TransitionResult(
        action="continue",
        outcome=None,
        next_body=None,
        matched_rule=None,
        passed=False,
    )


def _hydrate_loop_round_from_store(
    project_id: str,
    by_id: dict[str, dict],
    order: list[str],
    store: "Store",
) -> tuple[dict[str, "TaskOutcome"], set[str]]:
    """Resume：从 store 恢复已拆分子任务，并 seed 已完成任务的 outcome（避免重跑 step-1 等）。"""
    from common.process_types import TaskOutcome

    terminal = _TERMINAL_OK | _TERMINAL_BAD

    for tid in list(by_id.keys()):
        row = store.get_task(project_id, tid) or {}
        meta = row.get("meta") or {}
        children = list(meta.get("split_children") or [])
        if not children and row.get("status") == "cancelled":
            children = [
                str(r["task_id"])
                for r in store.list_tasks(project_id)
                if str(r.get("parent_id") or "") == tid
            ]
        if row.get("status") != "cancelled" or not children:
            continue
        parent = by_id.pop(tid, None)
        if parent is None:
            continue
        parent_deps = list(parent.get("dependencies") or [])
        loaded: list[str] = []
        for cid in children:
            if cid in by_id:
                loaded.append(cid)
                continue
            crow = store.get_task(project_id, cid)
            if not crow:
                continue
            cmeta = crow.get("meta") or {}
            child: dict = {
                "id": cid,
                "name": crow.get("name", ""),
                "agent": crow.get("agent", ""),
                "reviewer": crow.get("reviewer", ""),
                "task_type": crow.get("task_type", ""),
                "dependencies": crow.get("dependencies") or list(parent_deps),
                "description": cmeta.get("description", ""),
            }
            tpl = cmeta.get("template_id") or parent.get("template_id")
            if tpl:
                child["template_id"] = tpl
            by_id[cid] = child
            loaded.append(cid)
        for t in by_id.values():
            deps = t.get("dependencies") or []
            if tid in deps:
                t["dependencies"] = [d for d in deps if d != tid] + loaded

    order[:] = topological_order(list(by_id.values()))

    outcomes: dict[str, TaskOutcome] = {}
    done: set[str] = set()
    for tid in by_id:
        row = store.get_task(project_id, tid) or {}
        st = str(row.get("status") or "pending")
        if st in terminal:
            outcomes[tid] = TaskOutcome(tid, st)
            done.add(tid)
    return outcomes, done


def instantiate_round_body_tasks(
    spec: LoopSpec,
    round_num: int,
    *,
    goal_prefix: str = "",
    body_key: str | None = None,
) -> list[dict]:
    """将 loop body 模板实例化为单轮 task 列表（新 id、轮内 dependencies）。"""
    body_tpl = spec.body_for(body_key) if (body_key or spec.bodies) else spec.body
    if not body_tpl:
        body_tpl = spec.body_for(spec.default_body)
    body_ids = {str(t.get("id") or "").strip() for t in body_tpl}
    out: list[dict] = []
    for tpl in body_tpl:
        body_id = str(tpl.get("id") or "").strip()
        if not body_id:
            raise ValueError(f"loop「{spec.id}」body 任务缺少 id")
        tid = loop_body_task_id(spec.id, round_num, body_id)
        deps = [
            loop_body_task_id(spec.id, round_num, str(d).strip())
            for d in (tpl.get("dependencies") or [])
        ]
        desc = _inject_loop_vars(
            tpl.get("description", ""),
            loop_id=spec.id,
            round_num=round_num,
            max_rounds=spec.max_rounds,
        )
        if goal_prefix and desc:
            desc = goal_prefix + desc
        elif goal_prefix:
            desc = goal_prefix.rstrip()
        item = {k: v for k, v in tpl.items() if k not in ("dependencies", "description", "id")}
        item["id"] = tid
        item["dependencies"] = deps
        item["description"] = desc
        item["_loop_id"] = spec.id
        item["_loop_round"] = round_num
        item["_loop_body_id"] = body_id
        out.append(item)
    return out


def expand_loop_body_for_validation(spec: LoopSpec) -> list[dict]:
    """展开 body 供 plan_gate 校验 agent/task_type/DAG。"""
    tasks: list[dict] = []
    if spec.is_v2 and len(spec.bodies) > 1:
        for body_key in spec.bodies:
            tasks.extend(instantiate_round_body_tasks(spec, 1, body_key=body_key))
        return tasks
    if spec.is_v2 and spec.bodies:
        for r in range(1, spec.max_rounds + 1):
            tasks.extend(instantiate_round_body_tasks(spec, r, body_key=spec.default_body))
        return tasks
    for r in range(1, spec.max_rounds + 1):
        branch_spec = LoopSpec(
            id=spec.id,
            max_rounds=spec.max_rounds,
            body=spec.body,
            until=spec.until or spec.fallback_until,
        )
        tasks.extend(instantiate_round_body_tasks(branch_spec, r))
    return tasks


def _read_deliverable(project_id: str, task_id: str, task_type: str) -> str:
    base = task_deliverable_base(project_id, task_id, task_type)
    rel = artifact_rel_path(task_id, task_type)
    path = Path(base) / rel
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _resolve_body_tid(spec: LoopSpec, round_num: int, body_ref: str) -> str:
    return loop_body_task_id(spec.id, round_num, str(body_ref).strip())


def evaluate_until(
    spec: LoopSpec,
    round_num: int,
    round_outcomes: dict[str, "TaskOutcome"],
    store: "Store",
    project_id: str,
    body_task_types: dict[str, str],
) -> bool:
    """判定本轮是否满足 until（OR 语义）。任一条件满足即 True。"""
    for cond in spec.until:
        if not isinstance(cond, dict):
            continue
        ctype = str(cond.get("type") or "").strip()
        if ctype == "deliverable_marker":
            body_ref = str(cond.get("task") or "").strip()
            marker = str(cond.get("marker") or "")
            if not body_ref or not marker:
                continue
            tid = _resolve_body_tid(spec, round_num, body_ref)
            tt = body_task_types.get(tid, "")
            if marker in _read_deliverable(project_id, tid, tt):
                return True
        elif ctype == "gate_passed":
            body_ref = str(cond.get("task") or "").strip()
            if not body_ref:
                continue
            tid = _resolve_body_tid(spec, round_num, body_ref)
            o = round_outcomes.get(tid)
            if o and o.status == "completed":
                return True
        elif ctype == "task_status":
            body_ref = str(cond.get("task") or "").strip()
            want = str(cond.get("status") or "").strip()
            if not body_ref or not want:
                continue
            tid = _resolve_body_tid(spec, round_num, body_ref)
            o = round_outcomes.get(tid)
            if o and o.status == want:
                return True
        elif ctype == "review_passed":
            body_ref = str(cond.get("task") or "").strip()
            if not body_ref:
                continue
            tid = _resolve_body_tid(spec, round_num, body_ref)
            for row in store.list_interactions(project_id):
                if row.get("task_id") != tid or row.get("kind") != "review":
                    continue
                iid = row.get("interaction_id") or ""
                for ev in store.list_run_events(iid):
                    if ev.get("kind") != "review_done":
                        continue
                    payload = ev.get("payload") or {}
                    if payload.get("passed") is True:
                        return True
    return False


def loop_placeholder_outcome_status(spec: LoopSpec, *, passed: bool) -> str:
    """loop 占位 task 的终态。"""
    if passed:
        if spec.on_pass in ("complete", "completed"):
            return "completed"
        if spec.on_pass in _TERMINAL_OK | _TERMINAL_BAD:
            return spec.on_pass
        return "completed"
    if spec.on_exhaust in _TERMINAL_OK | _TERMINAL_BAD:
        return spec.on_exhaust
    return "needs_review"


def _apply_min_rounds_guard(
    spec: LoopSpec,
    round_num: int,
    result: TransitionResult,
) -> TransitionResult:
    """未达 min_rounds 时，非 pass 的 exit 强制 continue。"""
    if result.action != "exit" or round_num >= spec.min_rounds or result.passed:
        return result
    return TransitionResult(
        action="continue",
        outcome=None,
        next_body=spec.default_body,
        matched_rule=result.matched_rule,
        passed=False,
    )


def _matched_transition_marker(spec: LoopSpec, matched_rule: int | None) -> str:
    if matched_rule is None or matched_rule < 0 or matched_rule >= len(spec.transition):
        return ""
    return (spec.transition[matched_rule].marker or "").strip()


def run_loop(
    project_id: str,
    placeholder: dict,
    spec: LoopSpec,
    *,
    deps: RunLoopDeps,
    goal_prefix: str = "",
    goal_text: str = "",
    initial_state: LoopRoundState | None = None,
) -> "TaskOutcome":
    """Loop 主状态机：多轮 body 执行 + transition / until 判定。"""
    from common.process_types import TaskOutcome

    placeholder_id = placeholder["id"]
    loop_id = spec.id
    event_scope = f"{project_id}:loop:{loop_id}"

    if not goal_text.strip():
        meta = (deps.store.get_project(project_id) or {}).get("meta") or {}
        goal_text = str(meta.get("goal") or placeholder.get("goal") or "")

    state = initial_state or reconstruct_loop_state(deps.store, project_id, loop_id, spec)
    body_key = (state.body_key if state else spec.default_body) or spec.default_body
    next_body_key: str | None = state.next_body_key if state else None
    start_round = max(1, state.round if state else 1)
    rounds_used = state.rounds_used if state else 0
    use_transition = bool(spec.is_v2 and (spec.transition or spec.assess))

    for round_num in range(start_round, spec.max_rounds + 1):
        rounds_used = round_num
        if next_body_key:
            body_key = next_body_key
            next_body_key = None

        round_goal_prefix = goal_prefix if round_num == 1 else build_patch_goal_prefix(
            project_id, round_num, spec.id,
        )
        if round_num > 1:
            prev_work = resolve_work_task_id(spec, round_num - 1, body_key)
            cur_work = resolve_work_task_id(spec, round_num, body_key)
            seed_patch_baseline(project_id, prev_work, cur_work)

        round_tasks = instantiate_round_body_tasks(
            spec, round_num, goal_prefix=round_goal_prefix, body_key=body_key,
        )
        assess_tid = resolve_assess_task_id(spec, round_num, body_key)
        assess_inputs = resolve_assess_inputs(
            spec, project_id, round_num, body_key, deps.store, goal_text,
        )
        if assess_inputs:
            for task in round_tasks:
                if task["id"] == assess_tid:
                    base = (task.get("description") or "").strip()
                    task["description"] = f"{assess_inputs}\n\n{base}".strip() if base else assess_inputs
                    break

        deps.persist_tasks(project_id, round_tasks)

        by_id = {t["id"]: t for t in round_tasks}
        order = topological_order(round_tasks)
        round_outcomes, done = _hydrate_loop_round_from_store(
            project_id, by_id, order, deps.store,
        )
        body_types = {t["id"]: t.get("task_type", "") for t in by_id.values()}

        agents = sorted({
            str(t.get("agent") or "").strip()
            for t in by_id.values() if str(t.get("agent") or "").strip()
        })
        while len(done) < len(by_id):
            if deps.expand_ready:
                while deps.expand_ready(
                    project_id, by_id, order, round_outcomes, agents, cycle=round_num,
                ):
                    order[:] = topological_order(list(by_id.values()))
                    body_types = {t["id"]: t.get("task_type", "") for t in by_id.values()}

            from common.dag_dispatch import ready_tasks

            wave = ready_tasks(
                order, by_id, round_outcomes,
                needs_review_blocks=deps.needs_review_blocks,
            )
            wave = [tid for tid in wave if tid not in done]
            if not wave:
                break
            body_tid = wave[0]
            result = deps.execute_task(project_id, by_id[body_tid])
            round_outcomes[body_tid] = result.outcome
            done.add(body_tid)
            if result.triage_decision == "abort":
                return TaskOutcome(placeholder_id, "failed", "loop 内任务中止", round_num)
            if result.split_subtasks:
                for sub in result.split_subtasks:
                    by_id[sub["id"]] = sub
                order[:] = topological_order(list(by_id.values()))
                body_types = {t["id"]: t.get("task_type", "") for t in by_id.values()}

        if use_transition:
            result = evaluate_transition(
                spec,
                round_num=round_num,
                body_key=body_key,
                project_id=project_id,
                round_outcomes=round_outcomes,
                body_task_types=body_types,
                store=deps.store,
            )
            result = _apply_min_rounds_guard(spec, round_num, result)
        else:
            passed = evaluate_until(
                spec, round_num, round_outcomes, deps.store, project_id, body_types,
            )
            if passed:
                result = TransitionResult("exit", spec.on_pass, None, None, passed=True)
            elif round_num >= spec.max_rounds:
                result = TransitionResult("exit", spec.on_exhaust, None, None, passed=False)
            else:
                result = TransitionResult("continue", None, None, None, passed=False)

        work_tid = resolve_work_task_id(spec, round_num, body_key)
        marker = _matched_transition_marker(spec, result.matched_rule)

        deps.append_run_event(
            event_scope,
            "loop_round_assess",
            {
                "round": round_num,
                "body_key": body_key,
                "assess_task_id": assess_tid,
                "passed": result.passed,
                "action": result.action,
                "outcome": result.outcome,
                "matched_rule": result.matched_rule,
                "marker": marker,
            },
        )

        if deps.on_loop_round_done:
            try:
                deps.on_loop_round_done(
                    project_id, loop_id, round_num, result.passed, work_tid, assess_tid,
                )
            except Exception:
                pass

        deps.append_run_event(
            event_scope,
            "loop_round_done",
            {
                "round": round_num,
                "passed": result.passed,
                "body_key": body_key,
                "placeholder": placeholder_id,
            },
        )

        if result.action == "exit":
            deps.append_run_event(
                event_scope,
                "loop_finished",
                {
                    "state": "passed" if result.passed else "exhausted",
                    "rounds_used": round_num,
                },
            )
            if result.passed:
                deps.update_task_meta(
                    project_id,
                    placeholder_id,
                    summary=f"loop 通过（第 {round_num} 轮）",
                    loop_rounds=round_num,
                )
            status = loop_placeholder_outcome_status(spec, passed=result.passed)
            if result.outcome:
                if result.outcome in ("complete", "completed"):
                    status = "completed"
                elif result.outcome in _TERMINAL_OK | _TERMINAL_BAD:
                    status = result.outcome
            deps.set_task_status(project_id, placeholder_id, status)
            msg = "" if result.passed else "loop until 未满足"
            return TaskOutcome(placeholder_id, status, msg, round_num)

        if result.next_body:
            deps.append_run_event(
                event_scope,
                "loop_transition",
                {
                    "round": round_num,
                    "from_body": body_key,
                    "to_body": result.next_body,
                    "action": "continue",
                },
            )
            deps.append_run_event(
                event_scope,
                "branch_selected",
                {
                    "round": round_num,
                    "from_body": body_key,
                    "to_body": result.next_body,
                    "body_key": result.next_body,
                },
            )
            next_body_key = result.next_body

    deps.append_run_event(
        event_scope,
        "loop_finished",
        {"state": "exhausted", "rounds_used": rounds_used},
    )
    status = loop_placeholder_outcome_status(spec, passed=False)
    deps.set_task_status(project_id, placeholder_id, status)
    return TaskOutcome(placeholder_id, status, "loop until 未满足", rounds_used)


def topological_order(tasks: list[dict]) -> list[str]:
    """轮内 body DAG 拓扑序（与 plan_gate 一致）。"""
    from common.plan_gate import topological_order as _topo

    return _topo(tasks)


def _validate_body_template(spec: LoopSpec, body_tpl: list[dict], *, label: str) -> set[str]:
    body_ids = set()
    for t in body_tpl:
        bid = str(t.get("id") or "").strip()
        if not bid:
            raise ValueError(f"loop「{spec.id}」{label} 缺少 id")
        if bid in body_ids:
            raise ValueError(f"loop「{spec.id}」{label} id「{bid}」重复")
        body_ids.add(bid)
    for t in body_tpl:
        bid = str(t.get("id") or "").strip()
        for d in t.get("dependencies") or []:
            dep = str(d).strip()
            if dep not in body_ids:
                raise ValueError(
                    f"loop「{spec.id}」{label}「{bid}」依赖「{dep}」不在同 body 内",
                )
    return body_ids


def validate_loop_specs(
    loops: list[LoopSpec],
    tasks: list[dict],
    team: set[str],
) -> None:
    """校验 loops 定义与 tasks 引用；展开 body 做 plan_gate。"""
    from common.plan_gate import check_plan

    by_id = {s.id: s for s in loops}
    if len(by_id) != len(loops):
        raise ValueError("loops[].id 重复")

    for spec in loops:
        if spec.is_v2:
            for body_key, body_tpl in spec.bodies.items():
                _validate_body_template(spec, body_tpl, label=f"bodies.{body_key}")
            default_tpl = spec.body_for(spec.default_body)
            default_ids = {str(t.get("id") or "").strip() for t in default_tpl}
            if spec.assess:
                if spec.assess.ref not in default_ids:
                    raise ValueError(
                        f"loop「{spec.id}」assess.ref「{spec.assess.ref}」"
                        f"不在 default_body「{spec.default_body}」内",
                    )
            for idx, rule in enumerate(spec.transition):
                if rule.next_body and rule.next_body not in spec.bodies:
                    raise ValueError(
                        f"loop「{spec.id}」transition[{idx}] next_body「{rule.next_body}」"
                        f"不在 bodies 中",
                    )
                if rule.when == "deliverable_marker" and rule.task:
                    if rule.task not in default_ids:
                        raise ValueError(
                            f"loop「{spec.id}」transition[{idx}] task「{rule.task}」"
                            f"不在 default_body「{spec.default_body}」内",
                        )
        else:
            body_ids = _validate_body_template(spec, spec.body, label="body")
            for cond in spec.until:
                cref = str((cond or {}).get("task") or "").strip()
                if cref and cref not in body_ids:
                    raise ValueError(
                        f"loop「{spec.id}」until 引用 body 任务「{cref}」不存在",
                    )
        expanded = expand_loop_body_for_validation(spec)
        if spec.is_v2 and len(spec.bodies) > 1:
            for body_key, body_tpl in spec.bodies.items():
                branch_tasks = instantiate_round_body_tasks(spec, 1, body_key=body_key)
                result = check_plan(branch_tasks, team, check_capabilities=True)
                if not result.passed:
                    raise ValueError(
                        f"loop「{spec.id}」bodies.{body_key} 校验失败：{result.feedback}",
                    )
            continue
        result = check_plan(expanded, team, check_capabilities=True)
        if not result.passed:
            raise ValueError(
                f"loop「{spec.id}」body 展开校验失败：{result.feedback}",
            )

    for t in tasks:
        loop_ref = str(t.get("loop") or "").strip()
        if not loop_ref:
            continue
        if t.get("agent") or t.get("task_type"):
            raise ValueError(
                f"任务「{t.get('id')}」声明 loop 时不得同时指定 agent/task_type",
            )
        if loop_ref not in by_id:
            raise ValueError(f"任务「{t.get('id')}」引用未知 loop「{loop_ref}」")
