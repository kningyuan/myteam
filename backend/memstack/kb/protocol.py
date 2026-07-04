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
        source: str = "auto",
        created_by: str = "",
    ) -> str:
        """写入条目，返回 ``kb://<backend>/<id>``。

        source: "user"（用户手动写）| "agent"（Agent 沉淀）| "auto"（系统复盘）
        created_by: 创建者标识（用户 ID 或 Agent ID）
        """
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

    def update(
        self,
        ref: str,
        *,
        title: Optional[str] = None,
        content: Optional[str] = None,
        tags: Optional[list] = None,
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> bool:
        ...

    def delete(self, ref: str) -> bool:
        ...
