#!/usr/bin/env python3
"""L3 知识库后端注册表。"""
from __future__ import annotations

from typing import Optional, Type

from common.store.store import Store

from memstack.config import kb_backend_name
from memstack.kb.gbrain import GbrainKnowledgeBackend
from memstack.kb.protocol import KnowledgeBackend
from memstack.kb.sqlite import SqliteKnowledgeBackend

_KB_BACKENDS: dict[str, Type] = {
    "sqlite": SqliteKnowledgeBackend,
    "gbrain": GbrainKnowledgeBackend,
}


def list_kb_backends() -> list[str]:
    return sorted(_KB_BACKENDS.keys())


def register_kb_backend(name: str, cls: Type) -> None:
    """测试 / 扩展用 — 注册额外 KB adapter。"""
    _KB_BACKENDS[name.strip().lower()] = cls


def get_kb_backend(
    store: Optional[Store] = None,
    backend: Optional[str] = None,
) -> KnowledgeBackend:
    """按配置返回 KB 后端。优先级：参数 > skill_config > MEMORY_BACKEND > sqlite。"""
    name = (backend or kb_backend_name()).strip().lower()
    cls = _KB_BACKENDS.get(name)
    if cls is None:
        raise NotImplementedError(
            f"KB 后端 '{name}' 未注册。可用: {', '.join(list_kb_backends())}。"
        )
    if name == "sqlite":
        return cls(store)
    return cls(store)
