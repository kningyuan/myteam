#!/usr/bin/env python3
"""Context-Memory 第 3 层 · 长期记忆 / KB（D16）。

抽象 = `kb://` 引用 + **可插拔后端接口**（get(ref) / search(tags,text) / write(entry)）。
后端可配置（memory.backend）：
  - 默认 `sqlite`：自包含、可移植、可检视、schema 自控（落 store.memory 表）。
  - 可选 `gbrain` 或其他：接口已留，按需实现，不预先构建。

判责（D16）：检索 = 框架确定性；**蒸馏入库 = agent 能力**，框架编排「何时写」。
标准 / 验收标准**不进 KB**（在格式注册表 registry，单一出处）。
"""
from __future__ import annotations

import os
from typing import Optional, Protocol

from common.store import Store

KB_SCHEME = "kb://"


class MemoryBackend(Protocol):
    def write(self, project_id: str, title: str, content: str, *,
              task_id: str = "", tags: Optional[list] = None) -> str: ...

    def get(self, ref: str) -> Optional[dict]: ...

    def search(self, *, tags: Optional[list] = None, text: str = "",
               project_id: Optional[str] = None) -> list[dict]: ...


class SqliteMemory:
    """默认 KB 后端：包裹 store.memory 表。ref 形如 ``kb://sqlite/<id>``。"""

    name = "sqlite"

    def __init__(self, store: Optional[Store] = None):
        self.store = store or Store()

    def write(self, project_id: str, title: str, content: str, *,
              task_id: str = "", tags: Optional[list] = None) -> str:
        mid = self.store.memory_write(project_id, title, content, task_id=task_id, tags=tags)
        return f"{KB_SCHEME}{self.name}/{mid}"

    def get(self, ref: str) -> Optional[dict]:
        mid = self._parse_ref(ref)
        if mid is None:
            return None
        entry = self.store.memory_get(mid)
        if entry is not None:
            entry["ref"] = ref
        return entry

    def search(self, *, tags: Optional[list] = None, text: str = "",
               project_id: Optional[str] = None) -> list[dict]:
        out = self.store.memory_search(tags=tags, text=text, project_id=project_id)
        for e in out:
            e["ref"] = f"{KB_SCHEME}{self.name}/{e['id']}"
        return out

    def _parse_ref(self, ref: str) -> Optional[int]:
        if not ref.startswith(f"{KB_SCHEME}{self.name}/"):
            return None
        tail = ref[len(f"{KB_SCHEME}{self.name}/"):]
        return int(tail) if tail.isdigit() else None


def get_backend(store: Optional[Store] = None, backend: Optional[str] = None) -> MemoryBackend:
    """按配置返回 KB 后端实例（默认 sqlite）。

    backend 优先级：参数 > 环境变量 MEMORY_BACKEND > 默认 'sqlite'。
    """
    name = backend or os.environ.get("MEMORY_BACKEND", "sqlite")
    if name == "sqlite":
        return SqliteMemory(store)
    raise NotImplementedError(
        f"KB 后端 '{name}' 未实现（接口已留，按需实现，不预先构建——D16）。")
