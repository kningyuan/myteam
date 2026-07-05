#!/usr/bin/env python3
"""Agent id 治理 — 废弃别名映射 + auto_create 白名单。"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Iterable

from common.paths import BUSINESS_CONFIG_DIR, BUSINESS_DIR

# 历史 id → 当前名册 id（LLM / 旧文档常误用 researcher）
DEPRECATED_AGENT_ALIASES: dict[str, str] = {
    "researcher": "research",
}


def normalize_agent_id(agent_id: str) -> str:
    aid = (agent_id or "").strip()
    if not aid:
        return aid
    return DEPRECATED_AGENT_ALIASES.get(aid, aid)


def normalize_agent_ids(agent_ids: Iterable[str]) -> list[str]:
    """去重保序；researcher 与 research 并存时合并为 research。"""
    out: list[str] = []
    seen: set[str] = set()
    for raw in agent_ids:
        aid = normalize_agent_id(str(raw or "").strip())
        if not aid or aid in seen:
            continue
        seen.add(aid)
        out.append(aid)
    return out


def normalize_team(team: Iterable[str]) -> set[str]:
    return set(normalize_agent_ids(team))


def normalize_plan_tasks(tasks: list[dict]) -> list[dict]:
    """归一化 task 列表中的 agent id 字段（兼容 ``agent_id`` / ``agent`` 两种写法）。"""
    out: list[dict] = []
    for t in tasks:
        item = dict(t)
        raw = str(item.get("agent") or item.get("agent_id") or "").strip()
        if raw:
            item["agent"] = normalize_agent_id(raw)
        out.append(item)
    return out


@lru_cache(maxsize=1)
def _registry_agent_ids() -> frozenset[str]:
    path = BUSINESS_CONFIG_DIR / "agents_registry.json"
    if not path.is_file():
        return frozenset()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return frozenset()
    agents = raw.get("agents") if isinstance(raw, dict) else None
    if not isinstance(agents, dict):
        return frozenset()
    return frozenset(agents.keys())


@lru_cache(maxsize=1)
def _roster_template_ids() -> frozenset[str]:
    path = BUSINESS_DIR / "templates" / "business-roster.json"
    if not path.is_file():
        return frozenset()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return frozenset()
    agents = raw.get("agents") if isinstance(raw, dict) else None
    if not isinstance(agents, dict):
        return frozenset()
    return frozenset(agents.keys())


def allowed_auto_create_ids() -> frozenset[str]:
    """auto_create 仅允许名册模板或已写入 agents_registry 的 id（归一化后）。"""
    ids = set(_roster_template_ids()) | set(_registry_agent_ids())
    return frozenset(normalize_agent_id(a) for a in ids)


def assert_auto_create_allowed(agent_id: str) -> str:
    """归一化 agent id；不在白名单则抛错（禁止为 LLM 幻觉 id 建仓）。"""
    aid = normalize_agent_id(agent_id)
    if aid not in allowed_auto_create_ids():
        hint = ""
        if agent_id in DEPRECATED_AGENT_ALIASES:
            hint = f"（「{agent_id}」应使用「{DEPRECATED_AGENT_ALIASES[agent_id]}」）"
        raise RuntimeError(
            f"team_config 返回未注册 agent「{agent_id}」{hint}，禁止 auto_create。"
            f"请使用 business-roster 中的 id，或先写入 agents_registry.json。"
        )
    return aid


def partition_auto_create_candidates(agent_ids: Iterable[str]) -> tuple[list[str], list[str]]:
    """返回 (可创建, 拒绝) 列表（均已归一化、去重）。"""
    allowed: list[str] = []
    rejected: list[str] = []
    white = allowed_auto_create_ids()
    for raw in normalize_agent_ids(agent_ids):
        if raw in white:
            allowed.append(raw)
        else:
            rejected.append(raw)
    return allowed, rejected


def invalidate_agent_id_policy_cache() -> None:
    _registry_agent_ids.cache_clear()
    _roster_template_ids.cache_clear()
