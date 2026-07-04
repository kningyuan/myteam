#!/usr/bin/env python3
"""interactive 模式轻量 harness — 群聊/私聊注入 umbrella + 偏好 + Rubric 质量标准（无 POST）。"""
from __future__ import annotations

import logging

from execution_harness.backends.context_provider import (
    fetch_kb_entries,
    fetch_l1_hint,
    fetch_preferences,
)
from execution_harness.config import harness_enabled, interactive_harness_enabled
from execution_harness.injection.blocks import (
    append_kb_top_k,
    append_l1_block,
    append_preference_block,
    append_rubric_block,
    append_umbrella_skill_block,
)
from execution_harness.skill.umbrella import resolve_umbrella_skill, umbrella_skill_path

from execution_harness.pre.engineer_loop import ENGINEER_LOOP_BLOCK

logger = logging.getLogger("execution_harness.pre.interactive")


def build_interactive_harness_block(agent_id: str) -> str:
    """为 interactive chat 追加轻量 execute 质量块 + Rubric 标准 + 前置资产。"""
    if not harness_enabled() or not interactive_harness_enabled():
        return ""
    lines: list[str] = []
    try:
        from common.agent.agent_registry import get_agent_info

        info = get_agent_info(agent_id)
        task_types = list(info.get("task_types") or [])
        first_type = str(task_types[0]) if task_types else ""
        for tt in task_types:
            umbrella = resolve_umbrella_skill(str(tt))
            if not umbrella:
                continue
            sp = umbrella_skill_path(umbrella)
            if sp is not None:
                append_umbrella_skill_block(lines, umbrella, str(sp))
                break
        if not any("umbrella skill" in ln for ln in lines):
            skills = list(info.get("skills") or [])
            for sid in skills:
                sp = umbrella_skill_path(sid)
                if sp is not None:
                    append_umbrella_skill_block(lines, sid, str(sp))
                    break

        # 路径 E：前置资产加载（全量偏好 + Skill匹配 + 知识库检索）
        try:
            from execution_harness.pre.self_improve import merge_constraints
            constraints = merge_constraints(agent_id, first_type, "", store=None)
            if constraints.get("constraints_text"):
                lines.append(constraints["constraints_text"])
        except Exception as e:
            logger.warning("interactive merge_constraints 失败，跳过约束注入: %s", e)

        # 偏好注入（兼容保留）
        pref = fetch_preferences(agent_id=agent_id)
        append_preference_block(lines, pref)

        # L1 记忆注入
        hint = fetch_l1_hint(agent_id, "", store=None)
        append_l1_block(lines, hint)

        # KB 知识注入
        entries = fetch_kb_entries("", "", store=None, limit=3)
        append_kb_top_k(lines, entries)

        # Rubric 质量评分标准注入
        append_rubric_block(lines, task_type=first_type)

        # 通用工程师思维循环
        lines.append(ENGINEER_LOOP_BLOCK.strip())
    except Exception as e:
        logger.warning("build_interactive_harness_block failed: %s", e)
    return "\n".join(lines).strip()
