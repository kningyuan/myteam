#!/usr/bin/env python3
"""Workflow loop 运行时 — 条件循环编排（R-Loop）。

机制在此；循环定义在 business/workflows/*.yaml 的 loops 段。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from common.project_artifacts import artifact_rel_path, task_deliverable_base

if TYPE_CHECKING:
    from common.process_types import TaskOutcome
    from common.store import Store

_TERMINAL_OK = frozenset({"completed", "needs_review"})
_TERMINAL_BAD = frozenset({"failed", "blocked"})


@dataclass
class LoopSpec:
    id: str
    max_rounds: int = 5
    body: list[dict] = field(default_factory=list)
    until: list[dict] = field(default_factory=list)
    on_pass: str = "complete"
    on_exhaust: str = "needs_review"
    description: str = ""


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
        body = item.get("body")
        if not isinstance(body, list) or not body:
            raise ValueError(f"loop「{lid}」须定义非空 body")
        until = item.get("until")
        if not isinstance(until, list) or not until:
            raise ValueError(f"loop「{lid}」须定义非空 until")
        try:
            max_rounds = int(item.get("max_rounds", 5))
        except (TypeError, ValueError) as e:
            raise ValueError(f"loop「{lid}」max_rounds 无效") from e
        if max_rounds < 1:
            raise ValueError(f"loop「{lid}」max_rounds 须 ≥ 1")
        out.append(LoopSpec(
            id=lid,
            max_rounds=max_rounds,
            body=[dict(b) for b in body if isinstance(b, dict)],
            until=[dict(u) for u in until if isinstance(u, dict)],
            on_pass=str(item.get("on_pass") or "complete").strip() or "complete",
            on_exhaust=str(item.get("on_exhaust") or "needs_review").strip() or "needs_review",
            description=str(item.get("description") or "").strip(),
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


def instantiate_round_body_tasks(
    spec: LoopSpec,
    round_num: int,
    *,
    goal_prefix: str = "",
) -> list[dict]:
    """将 loop body 模板实例化为单轮 task 列表（新 id、轮内 dependencies）。"""
    body_ids = {str(t.get("id") or "").strip() for t in spec.body}
    out: list[dict] = []
    for tpl in spec.body:
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
    """展开全部轮次 body，供 plan_gate 校验 agent/task_type/DAG。"""
    tasks: list[dict] = []
    for r in range(1, spec.max_rounds + 1):
        tasks.extend(instantiate_round_body_tasks(spec, r))
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
        body_ids = set()
        for t in spec.body:
            bid = str(t.get("id") or "").strip()
            if not bid:
                raise ValueError(f"loop「{spec.id}」body 缺少 id")
            if bid in body_ids:
                raise ValueError(f"loop「{spec.id}」body id「{bid}」重复")
            body_ids.add(bid)
        for t in spec.body:
            bid = str(t.get("id") or "").strip()
            for d in t.get("dependencies") or []:
                dep = str(d).strip()
                if dep not in body_ids:
                    raise ValueError(
                        f"loop「{spec.id}」body「{bid}」依赖「{dep}」不在同 body 内",
                    )
        for cond in spec.until:
            cref = str((cond or {}).get("task") or "").strip()
            if cref and cref not in body_ids:
                raise ValueError(
                    f"loop「{spec.id}」until 引用 body 任务「{cref}」不存在",
                )
        expanded = expand_loop_body_for_validation(spec)
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
