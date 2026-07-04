#!/usr/bin/env python3
"""Plan gate — task DAG 确定性校验（纯函数，无 I/O）。"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional

from common.agent.agent_id_policy import normalize_plan_tasks, normalize_team
from common.gate.registry import get_spec


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
    tasks = normalize_plan_tasks(tasks)
    team = normalize_team(team)
    ids = [t.get("id", "") for t in tasks]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        return PlanCheckResult(False, f"任务 id 有重复：{', '.join(dupes)}")

    id_set = set(ids)
    exec_tasks = [t for t in tasks if not t.get("loop")]

    bad_agents = sorted({
        aid for t in exec_tasks
        for aid in [str(t.get("agent") or "").strip()]
        if aid and aid not in team
    })
    if bad_agents:
        return PlanCheckResult(False,
            f"以下 agent 不在团队名册中：{', '.join(bad_agents)}；"
            f"每个任务的 agent 只能从 [{', '.join(sorted(team))}] 中选。")

    bad_types = sorted({
        tt for t in exec_tasks
        for tt in [str(t.get("task_type") or "").strip()]
        if tt and get_spec(tt) is None
    })
    if bad_types:
        return PlanCheckResult(False,
            f"以下 task_type 未在注册表中：{', '.join(bad_types)}；"
            f"只能用已注册的类型。")

    if check_capabilities:
        from common.agent.agent_registry import agent_task_type_map
        cap_map = agent_task_type_map()
        cap_errors: list[str] = []
        for t in exec_tasks:
            aid = t.get("agent", "")
            tt = t.get("task_type", "")
            allowed = cap_map.get(aid)
            if aid not in cap_map:
                continue
            if not allowed:
                cap_errors.append(
                    f"{aid} 未配置可执行任务类型（请在管理 Tab → Agent 配置中勾选）",
                )
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


@dataclass
class PlanQuality:
    """task_plan DAG 质量评估（非阻塞，用于画像和 recurring 优化）。"""
    task_count: int = 0
    max_depth: int = 0
    max_fanout: int = 0
    type_diversity: float = 0.0
    dep_density: float = 0.0
    score: float = 1.0
    notes: list[str] = None

    def __post_init__(self):
        if self.notes is None:
            self.notes = []

    def to_dict(self) -> dict:
        return {
            "task_count": self.task_count,
            "max_depth": self.max_depth,
            "max_fanout": self.max_fanout,
            "type_diversity": round(self.type_diversity, 3),
            "dep_density": round(self.dep_density, 3),
            "score": round(self.score, 3),
            "notes": self.notes,
        }


def evaluate_plan_quality(tasks: list[dict]) -> PlanQuality:
    """评估 task DAG 的结构质量（非阻塞，仅记录画像）。

    指标：
    - max_depth：最长依赖链长度（过深 → 串行瓶颈）
    - max_fanout：单任务最大子任务数（过宽 → 协调困难）
    - type_diversity：unique task_types / total tasks（过低 → 粒度不均）
    - dep_density：依赖边数 / 任务数（过高 → 耦合过紧）
    - score：综合评分 0.0~1.0
    """
    tasks = normalize_plan_tasks(tasks)
    n = len(tasks)
    if n == 0:
        return PlanQuality()

    id_set = {t.get("id", "") for t in tasks}
    # 计算最大深度（最长路径）
    children_map: dict[str, list[str]] = {t["id"]: [] for t in tasks}
    parent_count: dict[str, int] = {t["id"]: 0 for t in tasks}
    for t in tasks:
        for dep in t.get("dependencies", []):
            if dep in id_set:
                children_map[dep].append(t["id"])
                parent_count[t["id"]] += 1

    # 拓扑层数 = 最大深度
    depth_map: dict[str, int] = {}
    queue = [tid for tid, c in parent_count.items() if c == 0]
    for tid in queue:
        depth_map[tid] = 1
    while queue:
        cur = queue.pop(0)
        for child in children_map.get(cur, []):
            depth_map[child] = max(depth_map.get(child, 0), depth_map[cur] + 1)
            parent_count[child] -= 1
            if parent_count[child] == 0:
                queue.append(child)
    max_depth = max(depth_map.values()) if depth_map else 1

    # 最大扇出
    max_fanout = max((len(v) for v in children_map.values()), default=0)

    # 类型多样性
    task_types = {str(t.get("task_type", "")).strip() for t in tasks if t.get("task_type")}
    type_diversity = len(task_types) / n if n > 0 else 0.0

    # 依赖密度
    total_deps = sum(len(t.get("dependencies", [])) for t in tasks)
    dep_density = total_deps / n if n > 0 else 0.0

    # 综合评分
    score = 1.0
    notes: list[str] = []
    if max_depth > 5:
        score -= 0.15
        notes.append(f"依赖链过深（{max_depth}层），可能造成串行瓶颈")
    if max_fanout > 6:
        score -= 0.1
        notes.append(f"单任务扇出过大（{max_fanout}），协调困难")
    if n > 12:
        score -= 0.1
        notes.append(f"任务数偏多（{n}），考虑合并或拆分为子项目")
    if type_diversity < 0.3 and n > 3:
        score -= 0.1
        notes.append("task_type 多样性低，粒度可能不均匀")
    if dep_density > 2.0:
        score -= 0.1
        notes.append(f"依赖密度高（{dep_density:.1f}），任务耦合过紧")
    score = max(0.0, min(1.0, score))

    return PlanQuality(
        task_count=n,
        max_depth=max_depth,
        max_fanout=max_fanout,
        type_diversity=type_diversity,
        dep_density=dep_density,
        score=score,
        notes=notes,
    )
