#!/usr/bin/env python3
"""task_type → umbrella methodology skill 映射。"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

from common.agent.agent_skills import skill_file_path
from execution_harness.config import task_type_skills_path

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_mapping() -> dict[str, dict]:
    """加载 task_type → {skill, skill_sections} 映射。

    YAML 支持两种值格式：
      - 字符串（旧）：``research: research_methodology``
      - dict（新）：``research: {skill: research_methodology, skill_sections: [框架, 验证]}``
    """
    path = task_type_skills_path()
    if not path.is_file():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        logger.warning("umbrella mapping 加载失败，回退空映射: %s", e)
        return {}
    if not isinstance(raw, dict):
        return {}
    defaults = raw.get("defaults")
    if not isinstance(defaults, dict):
        return {}
    result: dict[str, dict] = {}
    for k, v in defaults.items():
        key = str(k).strip()
        if not key:
            continue
        if isinstance(v, str):
            sid = v.strip()
            if sid:
                result[key] = {"skill": sid, "skill_sections": None}
        elif isinstance(v, dict):
            sid = str(v.get("skill", "")).strip()
            if sid:
                secs = v.get("skill_sections")
                if isinstance(secs, list):
                    secs = [str(s).strip() for s in secs if str(s).strip()]
                else:
                    secs = None
                result[key] = {"skill": sid, "skill_sections": secs or None}
    return result


def resolve_umbrella_skill(task_type: str) -> Optional[str]:
    tt = (task_type or "").strip()
    if not tt:
        return None
    entry = _load_mapping().get(tt)
    return entry["skill"] if entry else None


def resolve_umbrella_skill_sections(task_type: str) -> Optional[list[str]]:
    """返回 task_type 配置的 skill_sections（按 ## heading 截取的章节名列表）。

    无配置时返回 None（表示注入全文）。
    """
    tt = (task_type or "").strip()
    if not tt:
        return None
    entry = _load_mapping().get(tt)
    if not entry:
        return None
    return entry.get("skill_sections")


def umbrella_skill_path(skill_id: str) -> Optional[Path]:
    return skill_file_path(skill_id)


def reload_mapping() -> None:
    _load_mapping.cache_clear()
