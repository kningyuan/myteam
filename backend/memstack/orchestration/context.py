#!/usr/bin/env python3
"""facade 上下文 — Framework 与 hook 之间的稳定数据结构。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from common.store.store import Store
from memstack.l1.protocol import MemoryScope


@dataclass
class ChatTurnContext:
    scope: MemoryScope
    message: str
    owner_id: str = ""


@dataclass
class ExecuteInjectContext:
    lines: list[str]
    project_id: str
    task_type: str
    agent_id: str = ""
    owner_id: str = ""
    store: Optional[Store] = None
    limit: int = 3


@dataclass
class TaskSuccessContext:
    base_dir: Path
    project_id: str
    task_id: str
    task_type: str
    store: Store
    agent_id: str = ""
    gate_passed: bool = True


@dataclass
class ProjectCompleteContext:
    project_id: str
    store: Store
    status: str = "completed"


@dataclass
class ConsensusContext:
    group_id: str
    draft_text: str
    agenda: str = ""
    project_id: str = ""
    tags: list[str] = field(default_factory=lambda: ["best_practice", "consensus"])
