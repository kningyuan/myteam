#!/usr/bin/env python3
"""gbrain KB adapter — vendor 就绪时用 gbrain，否则降级 sqlite（仍可用）。"""
from __future__ import annotations

import logging
from typing import Optional

from memstack.config import vendor_path
from memstack.kb.protocol import KB_SCHEME
from memstack.kb.sqlite import SqliteKnowledgeBackend

logger = logging.getLogger("memstack.kb.gbrain")


class GbrainKnowledgeBackend:
    """gbrain 团队 KB；无 vendor 时透明降级 sqlite。"""

    name = "gbrain"

    def __init__(self, store=None):
        self._store = store
        self._gbrain = None
        root = vendor_path("gbrain")
        if root.is_dir():
            try:
                self._gbrain = self._load_gbrain(root, store)
            except Exception as e:
                logger.warning("gbrain vendor 加载失败，降级 sqlite: %s", e)
        if self._gbrain is None:
            logger.info("gbrain vendor 未安装，KB 使用 sqlite 降级")
            self._sqlite = SqliteKnowledgeBackend(store)
        else:
            self._sqlite = None

    @staticmethod
    def _load_gbrain(root, store):
        # vendor 接入点：vendors/gbrain 安装后在此 import 并返回客户端
        init_py = root / "__init__.py"
        if not init_py.is_file():
            return None
        # Phase 1+：from gbrain_client import GBrain; return GBrain(store=store)
        return None

    def _backend(self):
        if self._gbrain is not None:
            return self._gbrain
        return self._sqlite

    def write(self, project_id: str, title: str, content: str, *,
              task_id: str = "", tags: Optional[list] = None) -> str:
        backend = self._backend()
        ref = backend.write(project_id, title, content, task_id=task_id, tags=tags)
        if self._gbrain is None and ref.startswith(f"{KB_SCHEME}sqlite/"):
            return ref.replace(f"{KB_SCHEME}sqlite/", f"{KB_SCHEME}gbrain/", 1)
        return ref

    def get(self, ref: str) -> Optional[dict]:
        if self._gbrain is None and ref.startswith(f"{KB_SCHEME}gbrain/"):
            ref = ref.replace(f"{KB_SCHEME}gbrain/", f"{KB_SCHEME}sqlite/", 1)
        return self._backend().get(ref)

    def search(self, *, tags: Optional[list] = None, text: str = "",
               project_id: Optional[str] = None) -> list[dict]:
        entries = self._backend().search(tags=tags, text=text, project_id=project_id)
        if self._gbrain is None:
            for e in entries:
                r = e.get("ref", "")
                if r.startswith(f"{KB_SCHEME}sqlite/"):
                    e["ref"] = r.replace(f"{KB_SCHEME}sqlite/", f"{KB_SCHEME}gbrain/", 1)
        return entries
