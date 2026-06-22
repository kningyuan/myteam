#!/usr/bin/env python3
"""interactive 模式轻量 harness — 群聊/私聊注入 umbrella + 偏好（无 POST）。"""
from __future__ import annotations

import logging

from execution_harness.backends.context_provider import fetch_preferences
from execution_harness.config import harness_enabled, interactive_harness_enabled
from execution_harness.injection.blocks import append_preference_block, append_umbrella_skill_block
from execution_harness.skill.umbrella import resolve_umbrella_skill, umbrella_skill_path

logger = logging.getLogger("execution_harness.pre.interactive")


def build_interactive_harness_block(agent_id: str) -> str:
    """为 interactive chat 追加轻量 execute 质量块。"""
    if not harness_enabled() or not interactive_harness_enabled():
        return ""
    lines: list[str] = []
    try:
        from common.agent_registry import get_agent_info

        info = get_agent_info(agent_id)
        task_types = list(info.get("task_types") or [])
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
        pref = fetch_preferences(agent_id=agent_id)
        append_preference_block(lines, pref)
    except Exception as e:
        logger.warning("build_interactive_harness_block failed: %s", e)
    return "\n".join(lines).strip()
