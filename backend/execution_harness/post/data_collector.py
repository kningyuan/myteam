#!/usr/bin/env python3
"""全链路任务数据采集 — 执行中自动留存输出文本、工具检索记录、Skill调用日志等。"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TaskTrace:
    """单次任务的全链路追踪数据。"""
    task_id: str = ""
    task_type: str = ""
    agent_id: str = ""

    # 前置资产
    loaded_preferences: list[str] = field(default_factory=list)
    matched_skills: list[str] = field(default_factory=list)
    referenced_kb: list[str] = field(default_factory=list)
    execution_constraints: str = ""

    # 执行数据
    output_text: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    skill_logs: list[str] = field(default_factory=list)
    kb_fragments: list[str] = field(default_factory=list)
    iteration_round: int = 1
    token_usage: int = 0

    # 时间戳
    started_at: float = 0.0
    finished_at: float = 0.0


class DataCollector:
    """全链路数据采集器，事件驱动式记录执行过程。"""

    def __init__(self):
        self._trace = TaskTrace()
        self._trace.started_at = time.time()

    def set_task(self, task_id: str, task_type: str, agent_id: str) -> None:
        self._trace.task_id = task_id
        self._trace.task_type = task_type
        self._trace.agent_id = agent_id

    def record_preferences(self, prefs: list[str]) -> None:
        self._trace.loaded_preferences = list(prefs)

    def record_skills(self, skills: list[str]) -> None:
        self._trace.matched_skills = list(skills)

    def record_kb(self, kb_entries: list[str]) -> None:
        self._trace.referenced_kb = list(kb_entries)

    def record_constraints(self, constraints: str) -> None:
        self._trace.execution_constraints = constraints

    def record_output(self, text: str) -> None:
        self._trace.output_text = text

    def record_tool_call(self, tool: str, query: str, result_summary: str) -> None:
        self._trace.tool_calls.append({
            "tool": tool,
            "query": query,
            "result": result_summary[:200],
            "ts": time.time(),
        })

    def record_skill_log(self, skill_id: str, action: str) -> None:
        self._trace.skill_logs.append(f"{skill_id}:{action}")

    def record_kb_fragment(self, source: str, content_snippet: str) -> None:
        self._trace.kb_fragments.append(f"[{source}] {content_snippet[:100]}")

    def record_token_usage(self, tokens: int) -> None:
        self._trace.token_usage = max(self._trace.token_usage, tokens)

    def inc_iteration(self) -> None:
        self._trace.iteration_round += 1

    def finish(self) -> TaskTrace:
        self._trace.finished_at = time.time()
        return self._trace

    def to_report(self) -> dict:
        t = self._trace
        elapsed = max(0, t.finished_at - t.started_at)
        return {
            "task_id": t.task_id,
            "task_type": t.task_type,
            "agent_id": t.agent_id,
            "preferences_count": len(t.loaded_preferences),
            "skills_used": t.matched_skills,
            "kb_referenced": len(t.referenced_kb),
            "output_length": len(t.output_text),
            "tool_calls": len(t.tool_calls),
            "skill_logs": t.skill_logs,
            "kb_fragments": len(t.kb_fragments),
            "iterations": t.iteration_round,
            "token_usage": t.token_usage,
            "elapsed_seconds": round(elapsed, 1),
            "has_mermaid": "```mermaid" in t.output_text,
            "has_plantuml": "```plantuml" in t.output_text or "```puml" in t.output_text,
            "has_graphviz": "```graphviz" in t.output_text or "```dot" in t.output_text,
        }

    def json(self) -> str:
        return json.dumps(self.to_report(), ensure_ascii=False, indent=2)