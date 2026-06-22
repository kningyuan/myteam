#!/usr/bin/env python3
"""task_type → umbrella methodology skill 映射。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

from common.agent_skills import skill_file_path
from execution_harness.config import task_type_skills_path


@lru_cache(maxsize=1)
def _load_mapping() -> dict[str, str]:
    path = task_type_skills_path()
    if not path.is_file():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(raw, dict):
        return {}
    defaults = raw.get("defaults")
    if isinstance(defaults, dict):
        return {str(k).strip(): str(v).strip() for k, v in defaults.items() if str(k).strip() and str(v).strip()}
    return {}


def resolve_umbrella_skill(task_type: str) -> Optional[str]:
    tt = (task_type or "").strip()
    if not tt:
        return None
    return _load_mapping().get(tt)


def umbrella_skill_path(skill_id: str) -> Optional[Path]:
    return skill_file_path(skill_id)


def reload_mapping() -> None:
    _load_mapping.cache_clear()
