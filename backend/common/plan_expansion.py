#!/usr/bin/env python3
"""Plan 静态/动态递归展开 — evaluate 驱动的 DAG 折回编排。"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from common.agent_id_policy import normalize_agent_ids
from common.decision_pipeline import DecisionPipeline
from common.dag_dispatch import ready_tasks
from common.plan_gate import topological_order
from common.plan_splice import splice_subtasks
from common.process_types import ProcessConfig
from common.store import Store

if TYPE_CHECKING:
    from common.process_types import TaskOutcome


def _is_loop_placeholder(task: dict) -> bool:
    """Loop 锚点任务由 loop_runtime 展开，不参与 evaluate 静态/动态拆分。"""
    return bool(str(task.get("loop") or "").strip())


@dataclass
class PlanExpander:
    decision: DecisionPipeline
    store: Store
    config: ProcessConfig

    def _split_depth(self, project_id: str, task_id: str, task: Optional[dict] = None) -> int:
        if task is not None and task.get("split_depth") is not None:
            try:
                return int(task["split_depth"])
            except (TypeError, ValueError):
                pass
        row = self.store.get_task(project_id, task_id) or {}
        raw = (row.get("meta") or {}).get("split_depth", 0)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    def apply_split(
        self,
        project_id: str,
        by_id: dict[str, dict],
        order: list[str],
        parent_id: str,
        subs: list[dict],
        *,
        cycle: int = 0,
        source: str = "evaluate",
    ) -> None:
        """将 parent 折回为 subs，更新内存 DAG、store 与拓扑序。"""
        parent = by_id.get(parent_id)
        if parent is None:
            return
        depth = self._split_depth(project_id, parent_id, parent)
        if depth >= self.config.max_split_depth:
            # 超过最大深度，改为 abort 而非 split
            self.store.set_task_status(project_id, parent_id, "failed")
            self.store.append_run_event(
                f"{project_id}:{parent_id}:split_depth_exceeded",
                "task_split_blocked",
                {"parent": parent_id, "depth": depth, "max": self.config.max_split_depth},
            )
            return
        result = dict(by_id)
        splice_subtasks(result, parent, subs)
        for s in subs:
            result[s["id"]]["split_depth"] = depth + 1
        by_id.clear()
        by_id.update(result)
        order[:] = topological_order(list(by_id.values()))

        suffix = f":c{cycle}" if cycle else ""
        child_ids = [s["id"] for s in subs]
        self.store.set_task_status(project_id, parent_id, "cancelled")
        self.store.update_task_meta(
            project_id,
            parent_id,
            split_source=source,
            split_children=child_ids,
        )
        for s in subs:
            desc = s.get("description", "")
            meta: dict = {"split_depth": depth + 1, "split_parent": parent_id}
            if desc:
                meta["description"] = desc
            if s.get("loop"):
                meta["loop"] = s["loop"]
            self.store.upsert_task(
                project_id,
                s["id"],
                name=s.get("name", ""),
                agent=s.get("agent", ""),
                reviewer=s.get("reviewer", ""),
                task_type=s.get("task_type", ""),
                dependencies=s.get("dependencies", []),
                status="pending",
                parent_id=parent_id,
                meta=meta,
            )
        self.store.append_run_event(
            f"{project_id}:{parent_id}:{source}{suffix}",
            "task_split",
            {"parent": parent_id, "children": child_ids, "depth": depth, "source": source},
        )

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
            if _is_loop_placeholder(task):
                continue
            subs = self.decision.evaluate(project_id, task, agents, depth, cycle=cycle)
            if not subs:
                continue
            splice_subtasks(result, task, subs)
            for s in subs:
                result[s["id"]]["split_depth"] = depth + 1
            self.store.append_run_event(
                f"{project_id}:{tid}:evaluate{suffix}", "task_split",
                {"parent": tid, "children": [s["id"] for s in subs], "depth": depth})
            worklist.extend((s["id"], depth + 1) for s in subs)
        return list(result.values())

    def expand_ready(
        self,
        project_id: str,
        by_id: dict[str, dict],
        order: list[str],
        outcomes: dict[str, "TaskOutcome"],
        agents: list[str],
        *,
        cycle: int = 0,
    ) -> bool:
        """对当前波次可调度任务做 evaluate；若过大则当场拆分。返回是否发生过拆分。"""
        agents = normalize_agent_ids(agents)
        changed = False
        while True:
            wave = ready_tasks(
                order, by_id, outcomes,
                needs_review_blocks=self.config.needs_review_blocks,
            )
            split_tid: Optional[str] = None
            split_subs: Optional[list[dict]] = None
            for tid in wave:
                task = by_id.get(tid)
                if task is None:
                    continue
                if _is_loop_placeholder(task):
                    continue
                depth = self._split_depth(project_id, tid, task)
                if depth >= self.config.max_split_depth:
                    continue
                subs = self.decision.evaluate(project_id, task, agents, depth, cycle=cycle)
                if subs:
                    split_tid = tid
                    split_subs = subs
                    break
            if not split_tid or not split_subs:
                break
            self.apply_split(
                project_id, by_id, order, split_tid, split_subs,
                cycle=cycle, source="dispatch_evaluate",
            )
            changed = True
        return changed
