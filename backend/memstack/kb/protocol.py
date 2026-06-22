#!/usr/bin/env python3
"""L3 知识库协议 — kb:// 引用 + 可插拔后端。"""
from __future__ import annotations

from typing import Optional, Protocol

KB_SCHEME = "kb://"


class KnowledgeBackend(Protocol):
    """团队长期记忆 / KB。"""

    name: str

    def write(
        self,
        project_id: str,
        title: str,
        content: str,
        *,
        task_id: str = "",
        tags: Optional[list] = None,
    ) -> str:
        """写入条目，返回 ``kb://<backend>/<id>``。"""
        ...

    def get(self, ref: str) -> Optional[dict]:
        ...

    def search(
        self,
        *,
        tags: Optional[list] = None,
        text: str = "",
        project_id: Optional[str] = None,
    ) -> list[dict]:
        ...
