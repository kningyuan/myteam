#!/usr/bin/env python3
"""偏好后端注册表。"""
from __future__ import annotations

import os
from typing import Optional, Type

from memstack.config import preferences_backend_name
from memstack.preferences.mem0 import Mem0PreferenceBackend
from memstack.preferences.protocol import PreferenceBackend
from memstack.preferences.static import StaticPreferenceBackend

_PREF_BACKENDS: dict[str, Type] = {
    "static": StaticPreferenceBackend,
    "mem0": Mem0PreferenceBackend,
}


def list_preference_backends() -> list[str]:
    return sorted(_PREF_BACKENDS.keys())


def get_preference_backend(backend: Optional[str] = None) -> PreferenceBackend:
    name = (backend or preferences_backend_name()).strip().lower()
    if not name:
        name = os.environ.get("PREFERENCES_BACKEND", "static")
    cls = _PREF_BACKENDS.get(name)
    if cls is None:
        raise NotImplementedError(
            f"偏好后端 '{name}' 未注册。可用: {', '.join(list_preference_backends())}。"
        )
    return cls()
