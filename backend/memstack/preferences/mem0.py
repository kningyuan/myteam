#!/usr/bin/env python3
"""Mem0 偏好后端 adapter 桩 — Phase 1 对接。"""
from __future__ import annotations

import logging
import os

from memstack.config import vendor_path
from memstack.preferences.protocol import PreferenceRecord
from memstack.preferences.static import StaticPreferenceBackend

logger = logging.getLogger("memstack.preferences.mem0")


class Mem0PreferenceBackend:
    name = "mem0"

    def __init__(self) -> None:
        self._static = StaticPreferenceBackend()
        self._ready = bool(os.environ.get("MEM0_API_KEY", "").strip()) or vendor_path(
            "mem0"
        ).is_dir()

    def get_preferences(
        self,
        owner_id: str,
        *,
        agent_id: str = "",
    ) -> list[PreferenceRecord]:
        if not self._ready:
            return self._static.get_preferences(owner_id, agent_id=agent_id)
        # TODO Phase 1: mem0 preference API
        return self._static.get_preferences(owner_id, agent_id=agent_id)

    def format_block(
        self,
        owner_id: str,
        *,
        agent_id: str = "",
    ) -> str:
        prefs = self.get_preferences(owner_id, agent_id=agent_id)
        if not prefs:
            return ""
        lines = ["【用户偏好】"]
        for p in prefs:
            lines.append(p.value.strip())
        return "\n".join(lines)
