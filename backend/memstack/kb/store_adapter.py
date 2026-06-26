from __future__ import annotations

from typing import Optional, Protocol


class MemoryStore(Protocol):
    def memory_search(
        self, project_id=None, text="", tags=None
    ) -> list[dict]: ...
    def memory_get(self, memory_id: int) -> Optional[dict]: ...
    def memory_write(
        self, project_id, title, content, task_id="", tags=None
    ) -> int: ...
    def memory_delete(self, memory_id: int) -> bool: ...
    def memory_update(
        self,
        memory_id,
        title=None,
        content=None,
        tags=None,
        project_id=None,
        task_id=None,
    ) -> bool: ...
    def upsert_project(self, project_id, title="", status=""): ...


class SqliteStoreAdapter:
    """Wraps common.store.Store into MemoryStore protocol."""

    def __init__(self):
        from common.store import Store

        self._store = Store()

    def memory_search(self, project_id=None, text="", tags=None):
        return self._store.memory_search(
            project_id=project_id, text=text, tags=tags
        )

    def memory_get(self, memory_id: int) -> Optional[dict]:
        return self._store.memory_get(memory_id)

    def memory_write(self, project_id, title, content, task_id="", tags=None):
        return self._store.memory_write(
            project_id, title, content, task_id=task_id, tags=tags
        )

    def memory_delete(self, memory_id: int) -> bool:
        return self._store.memory_delete(memory_id)

    def memory_update(
        self,
        memory_id,
        title=None,
        content=None,
        tags=None,
        project_id=None,
        task_id=None,
    ):
        return self._store.memory_update(
            memory_id,
            title=title,
            content=content,
            tags=tags,
            project_id=project_id,
            task_id=task_id,
        )

    def upsert_project(self, project_id, title="", status=""):
        return self._store.upsert_project(project_id, title=title, status=status)

    def close(self):
        self._store.close()
