#!/usr/bin/env python3
"""默认 KB 后端：store.memory 表（sqlite）。"""
from __future__ import annotations

from typing import Optional

from memstack.kb.protocol import KB_SCHEME
from memstack.kb.store_adapter import MemoryStore, SqliteStoreAdapter
from memstack.kb.template import content_to_json, is_structured, json_to_content


class SqliteKnowledgeBackend:
    """ref 形如 ``kb://sqlite/<id>``。"""

    name = "sqlite"

    def __init__(self, store: Optional[MemoryStore] = None):
        self.store = store or SqliteStoreAdapter()

    def write(
        self,
        project_id: str,
        title: str,
        content: str,
        *,
        task_id: str = "",
        tags: Optional[list] = None,
        structured_content: Optional[dict[str, str]] = None,
    ) -> str:
        """写入 KB 条目。

        content: 纯文本（向后兼容）。
        structured_content: 结构化字典（按 task_type 模板分节），优先级高于 content。
        当 structured_content 不为 None 时，content 参数被忽略。
        """
        if structured_content is not None:
            store_content = content_to_json(structured_content)
        else:
            store_content = content
        mid = self.store.memory_write(
            project_id, title, store_content, task_id=task_id, tags=tags
        )
        return f"{KB_SCHEME}{self.name}/{mid}"

    def get(self, ref: str) -> Optional[dict]:
        mid = self._parse_ref(ref)
        if mid is None:
            return None
        entry = self.store.memory_get(mid)
        if entry is not None:
            entry["ref"] = ref
            content = entry.get("content", "")
            struct = json_to_content(content) if isinstance(content, str) else None
            if struct is not None:
                entry["content"] = content  # keep raw JSON
                entry["structured_content"] = struct
        return entry

    def search(
        self,
        *,
        tags: Optional[list] = None,
        text: str = "",
        project_id: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> list[dict]:
        out = self.store.memory_search(tags=tags, text=text, project_id=project_id)
        for entry in out:
            entry["ref"] = f"{KB_SCHEME}{self.name}/{entry['id']}"
            content = entry.get("content", "")
            struct = json_to_content(content) if isinstance(content, str) else None
            if struct is not None:
                entry["structured_content"] = struct
        return out

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
        mid = self._parse_ref(ref)
        if mid is None:
            return False
        return self.store.memory_update(
            mid,
            title=title,
            content=content,
            tags=tags,
            project_id=project_id,
            task_id=task_id,
        )

    def delete(self, ref: str) -> bool:
        mid = self._parse_ref(ref)
        if mid is None:
            return False
        return self.store.memory_delete(mid)

    def _parse_ref(self, ref: str) -> Optional[int]:
        if not ref.startswith(f"{KB_SCHEME}{self.name}/"):
            return None
        tail = ref[len(f"{KB_SCHEME}{self.name}/") :]
        return int(tail) if tail.isdigit() else None


# 兼容旧名
SqliteMemory = SqliteKnowledgeBackend
