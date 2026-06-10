#!/usr/bin/env python3
"""编排内核可选回调 — 群组同步、进度通报等（Hub 注入，CLI 可不传）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class ProjectHooks:
    on_team_ready: Optional[Callable[[str, list[str], str], None]] = None
    on_task_done: Optional[Callable[[str, str, str, str], None]] = None
    on_wave: Optional[Callable[[str, list[str]], None]] = None
