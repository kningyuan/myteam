#!/usr/bin/env python3
"""Plan 静态递归展开 — evaluate 驱动的 DAG 折回编排。"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from common.decision_pipeline import DecisionPipeline
from common.plan_splice import splice_subtasks
from common.process_types import ProcessConfig
from common.store import Store


@dataclass
class PlanExpander:
    decision: DecisionPipeline
    store: Store
    config: ProcessConfig

    def expand(self, project_id: str, tasks: list[dict],
               agents: list[str], *, cycle: int = 0) -> list[dict]:
        result: dict[str, dict] = {t["id"]: t for t in tasks}
        worklist = deque((t["id"], 0) for t in tasks)
        suffix = f":c{cycle}" if cycle else ""
        while worklist:
            tid, depth = worklist.popleft()
            if depth >= self.config.max_split_depth:
                continue
            task = result.get(tid)
            if task is None:
                continue
            subs = self.decision.evaluate(project_id, task, agents, depth, cycle=cycle)
            if not subs:
                continue
            splice_subtasks(result, task, subs)
            self.store.append_run_event(
                f"{project_id}:{tid}:evaluate{suffix}", "task_split",
                {"parent": tid, "children": [s["id"] for s in subs], "depth": depth})
            worklist.extend((s["id"], depth + 1) for s in subs)
        return list(result.values())
