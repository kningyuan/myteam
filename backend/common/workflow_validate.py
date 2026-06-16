#!/usr/bin/env python3
"""Workflow payload 保存前校验 — Hub API 前置闸门。

返回结构化错误列表（非 raise），供 API 层一次性返回所有问题给前端。
与现有 validate_workflow() 互补：本函数走快速失败路径收集错误，
write_workflow_raw → validate_workflow() 仍作第二道防线（raise）。

核心差异：
- validate_workflow(profile)  → 顺序校验，遇到第一个 ValueError 即终止
- validate_workflow_payload(data) → 累积所有错误，返回 list[str]
"""
from __future__ import annotations

from typing import Any, Optional

from common.agent_id_policy import normalize_agent_ids, normalize_plan_tasks
from common.loop_runtime import LoopSpec, iter_loop_body_tasks, parse_loop_specs, validate_loop_specs
from common.plan_gate import check_plan
from common.registry import get_spec
from common.workflow_loader import roster_from_tasks


def validate_workflow_payload(
    data: Any,
    *,
    available_agents: Optional[set[str]] = None,
) -> list[str]:
    """校验 workflow dict，返回所有验证错误。

    返回空列表表示校验通过。
    不修改 data，不执行磁盘 I/O。

    Args:
        data: 待校验的 workflow dict（来自 API body）。
        available_agents: 可选的已注册 agent 集合；不传则使用默认扫描。

    Returns:
        错误列表；空列表 = 通过。
    """
    errors: list[str] = []

    # Step 1: 基础结构校验
    errors.extend(_validate_basic_structure(data))

    if errors:
        # 结构错误无法继续，直接返回
        return errors

    # 归一化
    tasks = normalize_plan_tasks(data["tasks"])
    try:
        loops = parse_loop_specs(data.get("loops"))
    except ValueError as e:
        errors.append(str(e))
        return errors
    roster = normalize_agent_ids(roster_from_tasks(tasks, loops))

    # Step 2: task_type 存在性校验
    errors.extend(_validate_task_types(tasks))

    # Step 3: agent 合法性校验
    errors.extend(_validate_agents(tasks, loops, roster, available_agents))

    # Step 4: plan_gate 校验（DAG 环、依赖、能力边界等）
    errors.extend(_validate_plan_gate(tasks, roster))

    # Step 5: loop 校验
    errors.extend(_validate_loops(tasks, loops, roster, data.get("options")))

    return errors


def _validate_basic_structure(data: Any) -> list[str]:
    """校验基础结构：dict、id、tasks。"""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["workflow 必须是对象"]

    wid = (data.get("id") or "").strip()
    if not wid:
        errors.append("workflow 缺少 id")
    elif "/" in wid or ".." in wid or wid.startswith("."):
        errors.append("workflow id 非法")

    tasks = data.get("tasks")
    if not tasks or not isinstance(tasks, list) or len(tasks) == 0:
        errors.append("workflow 未定义 tasks")

    return errors


def _validate_task_types(tasks: list[dict]) -> list[str]:
    """校验每个任务的 task_type 是否已注册。"""
    errors: list[str] = []
    for t in tasks:
        if t.get("loop"):
            continue
        tt = str(t.get("task_type") or "").strip()
        tid = str(t.get("id") or "").strip()
        if not tt:
            errors.append(f"任务「{tid}」缺少 task_type")
        elif get_spec(tt) is None:
            errors.append(f"任务「{tid}」引用了未注册的 task_type「{tt}」")
    return errors


def _validate_agents(
    tasks: list[dict],
    loops: list,
    roster: list[str],
    available_agents: Optional[set[str]],
) -> list[str]:
    """校验每个任务的 agent 是否合法（在名册中）。"""
    from common.agent_registry import list_available_agent_ids

    errors: list[str] = []

    if available_agents is not None:
        # 测试时传入 mock 值
        agent_pool = available_agents
    else:
        # PGD bootstrap agents（内建协调者）
        agent_pool = set(list_available_agent_ids()) | _pgd_bootstrap_agent_ids()

    seen_tasks = set()
    for t in tasks:
        if t.get("loop"):
            continue
        aid = str(t.get("agent") or "").strip()
        tid = str(t.get("id") or "unknown").strip()
        if aid and aid not in agent_pool:
            errors.append(f"任务「{tid}」引用了不存在的 Agent「{aid}」")

    # Loop body 中的 agent
    for spec in loops:
        for t in iter_loop_body_tasks(spec):
            aid = str(t.get("agent") or "").strip()
            tid = str(t.get("id") or "unknown").strip()
            if aid and aid not in agent_pool:
                errors.append(f"Loop 任务「{tid}」引用了不存在的 Agent「{aid}」")

    return errors


def _validate_plan_gate(tasks: list[dict], roster: list[str]) -> list[str]:
    """调用 check_plan 做 DAG 确定性校验。"""
    errors: list[str] = []
    team = set(roster)
    if not tasks:
        return errors

    result = check_plan(tasks, team, check_capabilities=True)
    if not result.passed:
        errors.append(result.feedback)
    return errors


def _validate_loops(
    tasks: list[dict],
    loops: list,
    roster: list[str],
    options: Optional[dict],
) -> list[str]:
    """校验 loop 配置合法性。"""
    errors: list[str] = []
    team = set(roster)
    if not loops:
        return errors

    try:
        validate_loop_specs(loops, tasks, team)
    except ValueError as e:
        errors.append(str(e))

    if options and options.get("review_enabled"):
        errors.append(
            "workflow 同时启用 loops 与 review_enabled，"
            "建议 loop body 内显式 review 步"
        )

    return errors


def _pgd_bootstrap_agent_ids() -> set[str]:
    """PGD 阶段内建 bootstrap agent（管理 Tab 未创建时的占位名）。"""
    import json
    from common.paths import BUSINESS_DIR

    tpl = BUSINESS_DIR / "templates" / "pgd-agents.json"
    if not tpl.is_file():
        return set()
    try:
        raw = json.loads(tpl.read_text(encoding="utf-8"))
        return set((raw.get("agents") or {}).keys())
    except (OSError, json.JSONDecodeError):
        return set()
