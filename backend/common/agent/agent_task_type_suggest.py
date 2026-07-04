#!/usr/bin/env python3
"""根据 Agent 职责描述确定性推导可执行 task_type 列表（无 LLM、无 CLI）。"""
from __future__ import annotations

import json
import re
from typing import Any

from common.paths import BUSINESS_CONFIG_DIR
from common.gate.task_type_store import list_task_type_ids

_RULES_CACHE: dict | None = None


def _load_agent_rules() -> dict:
    global _RULES_CACHE
    if _RULES_CACHE is not None:
        return _RULES_CACHE
    path = BUSINESS_CONFIG_DIR / "agent_task_type_rules.json"
    if path.is_file():
        try:
            _RULES_CACHE = json.loads(path.read_text(encoding="utf-8"))
            return _RULES_CACHE
        except (OSError, json.JSONDecodeError):
            pass
    _RULES_CACHE = {"rules": [], "fallback_task_types": ["research"]}
    return _RULES_CACHE


def _norm(text: str) -> str:
    return (text or "").strip().lower()


def suggest_task_types_for_agent(
    description: str,
    *,
    name: str = "",
    agent_id: str = "",
) -> dict[str, Any]:
    """从 Agent 描述推导 task_types；返回 {task_types, matched_rules}。"""
    blob = _norm(f"{name} {agent_id} {description}")
    if not blob:
        raise ValueError("描述不能为空")

    cfg = _load_agent_rules()
    known = set(list_task_type_ids())
    hits: list[str] = []
    matched: list[str] = []

    for rule in cfg.get("rules") or []:
        keywords = rule.get("keywords") or []
        tts = rule.get("task_types") or []
        if any(kw.lower() in blob for kw in keywords):
            matched.append(keywords[0] if keywords else "")
            for t in tts:
                if t in known and t not in hits:
                    hits.append(t)

    for tid in known:
        if re.search(rf"\b{re.escape(tid)}\b", blob) and tid not in hits:
            hits.append(tid)

    if not hits:
        hits = list(cfg.get("fallback_task_types") or ["research"])

    return {"task_types": hits, "matched_rules": matched}
