#!/usr/bin/env python3
"""Plan gate — task DAG 确定性校验（纯函数，无 I/O）。"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional

from common.registry import get_spec


@dataclass
class PlanCheckResult:
    """plan gate 校验结果。passed=False 时 feedback 包含给 agent 的打回理由。"""
    passed: bool
    feedback: str = ""


def topological_order(tasks: list[dict]) -> list[str]:
    """Kahn 拓扑排序，返回任务 id 顺序；存在环则抛 ValueError。"""
    ids = {t["id"] for t in tasks}
    indeg = {t["id"]: 0 for t in tasks}
    graph: dict[str, list[str]] = {t["id"]: [] for t in tasks}
    for t in tasks:
        for dep in t.get("dependencies", []):
            if dep not in ids:
                raise ValueError(f"依赖 {dep} 未在任务列表中")
            graph[dep].append(t["id"])
            indeg[t["id"]] += 1
    queue = deque(sorted(tid for tid, d in indeg.items() if d == 0))
    order: list[str] = []
    while queue:
        n = queue.popleft()
        order.append(n)
        for m in graph[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    if len(order) != len(ids):
        raise ValueError("任务依赖存在环")
    return order


def prefix_cycle(tasks: list[dict], cycle: int) -> list[dict]:
    """给一轮任务的 id 与依赖加 ``cN_`` 前缀，避免跨周期覆盖、便于可观测区分轮次。"""
    pref = f"c{cycle}_"
    return [{**t, "id": pref + t["id"],
             "dependencies": [pref + d for d in t.get("dependencies", [])]} for t in tasks]


def check_plan(tasks: list[dict], team: set[str], *,
               max_fanout: Optional[int] = None,
               check_capabilities: bool = True) -> PlanCheckResult:
    """确定性门禁：校验 task DAG 的 agent/类型/依赖/无环/扇出。"""
    ids = [t.get("id", "") for t in tasks]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        return PlanCheckResult(False, f"任务 id 有重复：{', '.join(dupes)}")

    id_set = set(ids)

    bad_agents = sorted({t.get("agent", "") for t in tasks
                         if t.get("agent", "") not in team})
    if bad_agents:
        return PlanCheckResult(False,
            f"以下 agent 不在团队名册中：{', '.join(bad_agents)}；"
            f"每个任务的 agent 只能从 [{', '.join(sorted(team))}] 中选。")

    bad_types = sorted({t.get("task_type", "") for t in tasks
                        if get_spec(t.get("task_type", "")) is None})
    if bad_types:
        return PlanCheckResult(False,
            f"以下 task_type 未在注册表中：{', '.join(bad_types)}；"
            f"只能用已注册的类型。")

    if check_capabilities:
        from common.agent_registry import agent_task_type_map
        cap_map = agent_task_type_map()
        cap_errors: list[str] = []
        for t in tasks:
            aid = t.get("agent", "")
            tt = t.get("task_type", "")
            allowed = cap_map.get(aid)
            # 未在注册表或 task_types 为空 → 不施加能力边界（向后兼容旧 agent）
            if not allowed:
                continue
            if tt not in allowed:
                cap_errors.append(
                    f"{aid} 不能执行 task_type「{tt}」（仅允许：{', '.join(allowed)}）")
        if cap_errors:
            return PlanCheckResult(False,
                "以下任务违反 agent 能力边界：\n- " + "\n- ".join(sorted(cap_errors)))

    dangling = sorted({d for t in tasks for d in t.get("dependencies", [])
                       if d not in id_set})
    if dangling:
        return PlanCheckResult(False,
            f"依赖引用了不存在的任务 id：{', '.join(dangling)}；"
            f"请仅引用本批次内的任务。")

    try:
        topological_order(tasks)
    except ValueError:
        return PlanCheckResult(False, "任务依赖存在环，请重新规划。")

    if max_fanout is not None and len(tasks) > max_fanout:
        return PlanCheckResult(False,
            f"子任务数 {len(tasks)} 超过上限 {max_fanout}，请合并。")

    return PlanCheckResult(True)
