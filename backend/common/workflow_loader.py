#!/usr/bin/env python3
"""Workflow profile 加载与实例化 — PGD 阶段闸门 DAG 种子。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from common.paths import BUSINESS_DIR
from common.plan_gate import check_plan


@dataclass
class WorkflowProfile:
    id: str
    version: str
    description: str
    roster: list[str]
    tasks: list[dict]
    options: dict[str, Any] = field(default_factory=dict)
    phases: list[dict] = field(default_factory=list)

    def instantiate_tasks(self, *, goal: str = "") -> list[dict]:
        """复制 task 列表，将 goal 注入 description。"""
        prefix = f"【项目目标】{goal.strip()}\n\n" if goal.strip() else ""
        out: list[dict] = []
        for t in self.tasks:
            item = {k: v for k, v in t.items() if k != "phase"}
            desc = item.get("description", "")
            if prefix and desc:
                item["description"] = prefix + desc
            elif prefix:
                item["description"] = prefix.rstrip()
            out.append(item)
        return out


def workflows_dir() -> Path:
    return BUSINESS_DIR / "workflows"


def list_workflows() -> list[str]:
    d = workflows_dir()
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.yaml"))


def load_workflow(workflow_id: str, *, path: Optional[Path] = None) -> WorkflowProfile:
    """按 id（文件名不含扩展名）或绝对路径加载 workflow。"""
    if path is not None:
        fp = path
    else:
        fp = workflows_dir() / f"{workflow_id}.yaml"
        if not fp.is_file():
            available = ", ".join(list_workflows()) or "（无）"
            raise FileNotFoundError(
                f"未找到 workflow「{workflow_id}」（{fp}）。可用：{available}")

    raw = yaml.safe_load(fp.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"workflow 格式无效：{fp}")

    wid = raw.get("id") or workflow_id
    roster_block = raw.get("roster") or {}
    required = roster_block.get("required") or []
    optional = roster_block.get("optional") or []
    roster = list(dict.fromkeys([*required, *optional]))
    if "main" not in roster:
        roster.insert(0, "main")

    tasks = raw.get("tasks") or []
    if not tasks:
        raise ValueError(f"workflow「{wid}」未定义 tasks")

    profile = WorkflowProfile(
        id=wid,
        version=str(raw.get("version", "1.0")),
        description=str(raw.get("description", "")).strip(),
        roster=roster,
        tasks=tasks,
        options=dict(raw.get("options") or {}),
        phases=list(raw.get("phases") or []),
    )
    validate_workflow(profile)
    return profile


def validate_workflow(profile: WorkflowProfile) -> None:
    """用 plan_gate 校验 roster 与 task DAG（不访问 agent_registry 能力表）。"""
    team = set(profile.roster)
    instantiated = profile.instantiate_tasks()
    result = check_plan(instantiated, team, check_capabilities=False)
    if not result.passed:
        raise ValueError(f"workflow「{profile.id}」DAG 校验失败：{result.feedback}")
