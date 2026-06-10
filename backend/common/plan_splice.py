#!/usr/bin/env python3
"""Plan 子任务 DAG 折回纯函数 — 无 I/O、无编排依赖。"""
from __future__ import annotations

from common.agent_id_policy import normalize_agent_id
from common.plan_gate import check_plan


def normalize_subtasks(subs: list[dict], parent: dict) -> list[dict]:
    pid = parent["id"]
    out: list[dict] = []
    for s in subs:
        out.append({
            "id": f"{pid}.{s['id']}",
            "name": s.get("name", ""),
            "agent": normalize_agent_id(s.get("agent") or parent.get("agent", "")),
            "task_type": s.get("task_type") or parent.get("task_type", ""),
            "description": s.get("description", ""),
            "reviewer": s.get("reviewer", ""),
            "dependencies": [f"{pid}.{d}" for d in (s.get("dependencies") or [])],
        })
    return out


def validate_subtasks(subs: list[dict], team: set[str], *, max_fanout: int) -> str:
    return check_plan(subs, team, max_fanout=max_fanout).feedback


def splice_subtasks(result: dict[str, dict], parent: dict, subs: list[dict]) -> None:
    """将 parent 替换为 subs，并修正其余任务对 parent 的依赖引用。"""
    pid = parent["id"]
    parent_deps = list(parent.get("dependencies", []))
    sub_ids = [s["id"] for s in subs]
    for s in subs:
        if not s["dependencies"]:
            s["dependencies"] = list(parent_deps)
        result[s["id"]] = s
    del result[pid]
    for t in result.values():
        deps = t.get("dependencies", [])
        if pid in deps:
            t["dependencies"] = [d for d in deps if d != pid] + sub_ids
