#!/usr/bin/env python3
"""从 business/hooks/ 按文件名加载 Python hook（Kernel 不 import business 包）。"""
from __future__ import annotations

import importlib.util
import sys
from types import ModuleType
from typing import Optional

from common.paths import BUSINESS_DIR

_CACHE: dict[str, ModuleType] = {}


def load_business_hook(module_name: str) -> Optional[ModuleType]:
    """加载 business/hooks/<module_name>.py；不存在返回 None。"""
    name = (module_name or "").strip()
    if not name:
        return None
    if name in _CACHE:
        return _CACHE[name]
    path = BUSINESS_DIR / "hooks" / f"{name}.py"
    if not path.is_file():
        return None
    mod_id = f"myteam_business_hook_{name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(mod_id, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_id] = mod
    spec.loader.exec_module(mod)
    _CACHE[name] = mod
    return mod
