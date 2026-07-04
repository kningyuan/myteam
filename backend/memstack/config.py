#!/usr/bin/env python3
"""memstack 路径与配置读取（运行态 config 不入库）。"""
from __future__ import annotations

import os
from pathlib import Path

from common.paths import BACKEND_DIR, CONFIG_DIR

MEMSTACK_DIR = BACKEND_DIR / "memstack"
VENDORS_DIR = MEMSTACK_DIR / "vendors"
VENDOR_MANIFEST = VENDORS_DIR / "manifest.yaml"


def _skill_config() -> dict:
    path = CONFIG_DIR / "skill_config.json"
    if not path.is_file():
        return {}
    try:
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _memstack_section() -> dict:
    raw = _skill_config().get("memstack")
    if isinstance(raw, dict):
        return dict(raw)
    # 兼容旧段名
    raw = _skill_config().get("memory")
    return dict(raw) if isinstance(raw, dict) else {}


def memstack_enabled(default: bool = True) -> bool:
    sec = _memstack_section()
    if "enabled" in sec:
        return bool(sec.get("enabled"))
    return default


def kb_backend_name(default: str = "sqlite") -> str:
    sec = _memstack_section()
    name = (sec.get("kb_backend") or os.environ.get("MEMORY_BACKEND") or default).strip()
    return name or default


def l1_backend_name(default: str = "sqlite") -> str:
    sec = _memstack_section()
    name = sec.get("l1_backend")
    if not name:
        am = _skill_config().get("agent_memory")
        if isinstance(am, dict):
            name = am.get("backend")
    name = (name or os.environ.get("AGENT_MEMORY_BACKEND") or default).strip()
    return name or default


def preferences_backend_name(default: str = "static") -> str:
    sec = _memstack_section()
    name = (
        sec.get("preferences_backend")
        or os.environ.get("PREFERENCES_BACKEND")
        or default
    ).strip()
    return name or default


def inject_top_k(default: int = 3) -> int:
    sec = _memstack_section()
    try:
        return max(0, int(sec.get("inject_top_k", default)))
    except (TypeError, ValueError):
        return default


def require_gate_pass_for_promote(default: bool = True) -> bool:
    sec = _memstack_section()
    raw = sec.get("require_gate_pass_for_promote", default)
    return bool(raw) if raw is not None else default


def anysearch_home() -> str:
    sec = _memstack_section()
    home = (sec.get("anysearch_home") or os.environ.get("ANYSEARCH_HOME") or "").strip()
    return home


def vendor_path(vendor_id: str) -> Path:
    return VENDORS_DIR / vendor_id
