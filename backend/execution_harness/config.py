#!/usr/bin/env python3
"""execution_harness 配置 — 读 config/skill_config.json execution_harness 段。"""
from __future__ import annotations

import logging
from pathlib import Path

from common.paths import BACKEND_DIR, CONFIG_DIR, MYTEAM_ROOT

logger = logging.getLogger(__name__)

HARNESS_DIR = BACKEND_DIR / "execution_harness"
TASK_TYPE_SKILLS_FILE = MYTEAM_ROOT / "business" / "config" / "task_type_skills.yaml"
PENDING_SKILLS_DIR = MYTEAM_ROOT / "business" / "skills" / "_pending"


def _skill_config() -> dict:
    path = CONFIG_DIR / "skill_config.json"
    if not path.is_file():
        return {}
    try:
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("skill_config.json 解析失败，回退空配置: %s", e)
        return {}


def _section() -> dict:
    raw = _skill_config().get("execution_harness")
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def harness_enabled(default: bool = True) -> bool:
    sec = _section()
    if "enabled" in sec:
        return bool(sec.get("enabled"))
    return default


def execute_harness_enabled(default: bool = True) -> bool:
    sec = _section()
    if "execute_harness_enabled" in sec:
        return bool(sec.get("execute_harness_enabled"))
    return harness_enabled(default=default)


def memory_char_limit(default: int = 2200) -> int:
    sec = _section()
    try:
        return max(256, int(sec.get("memory_char_limit", default)))
    except (TypeError, ValueError):
        return default


def user_char_limit(default: int = 1375) -> int:
    sec = _section()
    try:
        return max(128, int(sec.get("user_char_limit", default)))
    except (TypeError, ValueError):
        return default


def inject_top_k(default: int = 3) -> int:
    sec = _section()
    try:
        return max(0, int(sec.get("inject_top_k", default)))
    except (TypeError, ValueError):
        return default


def l1_on_execute(default: bool = True) -> bool:
    sec = _section()
    if "l1_on_execute" in sec:
        return bool(sec.get("l1_on_execute"))
    return default


def kb_enabled(default: bool = True) -> bool:
    sec = _section()
    if "kb_enabled" in sec:
        return bool(sec.get("kb_enabled"))
    return default


def kb_inject_allowed() -> bool:
    """KB 注入需 harness 允许且 memstack KB 后端可用（memstack.enabled）。"""
    if not kb_enabled():
        return False
    try:
        from memstack.config import memstack_enabled

        return memstack_enabled(default=True)
    except Exception as e:
        logger.warning("kb_inject_allowed memstack 可用性检查失败，回退 False: %s", e)
        return False


def skill_review_enabled(default: bool = True) -> bool:
    sec = _section()
    if "skill_review_enabled" in sec:
        return bool(sec.get("skill_review_enabled"))
    return default


def skill_review_min_attempts(default: int = 1) -> int:
    """Gate 重试次数达到此值时更易触发 review（复杂任务信号）。"""
    sec = _section()
    try:
        return max(1, int(sec.get("skill_review_after_gate_retries", default)))
    except (TypeError, ValueError):
        return default


def skills_write_approval(default: bool = True) -> bool:
    sec = _section()
    if "skills_write_approval" in sec:
        return bool(sec.get("skills_write_approval"))
    return default


def task_type_skills_path() -> Path:
    sec = _section()
    raw = (sec.get("task_type_skills_path") or "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else MYTEAM_ROOT / raw
    return TASK_TYPE_SKILLS_FILE


def experience_clip_chars(default: int = 400) -> int:
    sec = _section()
    try:
        return max(80, int(sec.get("experience_clip_chars", default)))
    except (TypeError, ValueError):
        return default


def ledger_distill_enabled(default: bool = True) -> bool:
    sec = _section()
    if "ledger_distill_enabled" in sec:
        return bool(sec.get("ledger_distill_enabled"))
    return default


def preferences_on_execute(default: bool = True) -> bool:
    """execute 注入 USER 偏好（不依赖 memstack.enabled）。"""
    sec = _section()
    if "preferences_on_execute" in sec:
        return bool(sec.get("preferences_on_execute"))
    return default


def interactive_harness_enabled(default: bool = True) -> bool:
    """群聊/私聊 interactive 轻量 harness（umbrella + 偏好）。"""
    sec = _section()
    if "interactive_harness_enabled" in sec:
        return bool(sec.get("interactive_harness_enabled"))
    return default


def lesson_promote_enabled(default: bool = True) -> bool:
    """POST — 任务有 retry 时自动写入 lesson 到 KB。"""
    sec = _section()
    if "lesson_promote_enabled" in sec:
        return bool(sec.get("lesson_promote_enabled"))
    return default


def lesson_inject_enabled(default: bool = True) -> bool:
    """PRE — 同类任务 lesson 注入。"""
    sec = _section()
    if "lesson_inject_enabled" in sec:
        return bool(sec.get("lesson_inject_enabled"))
    return default
