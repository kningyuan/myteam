#!/usr/bin/env python3
"""execution_harness 上下文 dataclass。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from common.store import Store


@dataclass
class ExecuteHarnessContext:
    """execute 前 harness 准备上下文。"""

    agent_id: str
    project_id: str
    task_id: str = ""
    task_type: str = ""
    owner_id: str = ""
    workspace: Optional[Path] = None
    lines: list[str] = field(default_factory=list)
    limit: int = 3
    store: Optional[Store] = None
    intent: str = ""


@dataclass
class TaskCompleteContext:
    """execute 成功后 POST 钩子上下文。"""

    project_id: str
    task_id: str
    task_type: str
    agent_id: str
    base_dir: Path
    store: Store
    gate_passed: bool = True
    interaction_id: str = ""
    attempt: int = 1
    status: str = "completed"


@dataclass
class SkillReviewContext:
    """Background skill review 输入。"""

    project_id: str
    task_id: str
    task_type: str
    agent_id: str
    interaction_id: str
    attempt: int
    deliverable_path: str = ""
    session_summary: str = ""
