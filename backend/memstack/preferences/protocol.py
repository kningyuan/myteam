#!/usr/bin/env python3
"""偏好 Protocol — Framework 层。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class PreferenceRecord:
    owner_id: str
    key: str
    value: str
    source: str = "static"


@runtime_checkable
class PreferenceBackend(Protocol):
    name: str

    def get_preferences(
        self,
        owner_id: str,
        *,
        agent_id: str = "",
    ) -> list[PreferenceRecord]:
        ...

    def format_block(
        self,
        owner_id: str,
        *,
        agent_id: str = "",
    ) -> str:
        """返回可注入 prompt 的偏好块（空串表示无）。"""
        ...
