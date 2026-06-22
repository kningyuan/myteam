#!/usr/bin/env python3
"""Shim — L3 KB 实现已迁至 memstack.kb。"""
from __future__ import annotations

from typing import Optional

from common.store import Store
from memstack.kb import KB_SCHEME, KnowledgeBackend, get_kb_backend
from memstack.kb.sqlite import SqliteKnowledgeBackend

MemoryBackend = KnowledgeBackend
SqliteMemory = SqliteKnowledgeBackend


def get_backend(store: Optional[Store] = None, backend: Optional[str] = None) -> MemoryBackend:
    return get_kb_backend(store, backend)
