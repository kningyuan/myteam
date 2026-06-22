#!/usr/bin/env python3
"""static 偏好后端 — 读 USER.md / skill 静态配置。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from common.paths import CONFIG_DIR
from memstack.preferences.protocol import PreferenceRecord
from memstack.preferences.sectioned import format_block as sectioned_format
from memstack.preferences.sectioned import to_records


class StaticPreferenceBackend:
    name = "static"

    def __init__(self):
        self._text_cache: Optional[str] = None

    def _read_user_md(self) -> str:
        if self._text_cache is not None:
            return self._text_cache
        path = CONFIG_DIR / "USER.md"
        if not path.is_file():
            return ""
        self._text_cache = path.read_text(encoding="utf-8", errors="replace").strip()
        return self._text_cache

    def _clear_cache(self):
        self._text_cache = None

    def _user_md_path(self, owner_id: str) -> Path:
        return CONFIG_DIR / "USER.md"

    def get_preferences(
        self,
        owner_id: str,
        *,
        agent_id: str = "",
        sections: Optional[list[str]] = None,
    ) -> list[PreferenceRecord]:
        """获取偏好记录。支持按 section 过滤。

        sections=None 返回全部记录（分节模式）。
        无分节的旧格式 USER.md 仍返回 key=USER.md 的单条记录（兼容）。
        """
        text = self._read_user_md()
        if not text:
            return []
        records = to_records(text, owner_id=owner_id, agent_id=agent_id)
        if sections is not None:
            section_set = {s.strip().lower() for s in sections}
            records = [r for r in records if r.key.strip().lower() in section_set]
        return records

    def format_block(
        self,
        owner_id: str,
        *,
        agent_id: str = "",
        sections: Optional[list[str]] = None,
    ) -> str:
        """返回可注入 prompt 的偏好块。

        sections=None 输出全部记录（默认，向后兼容）。
        sections=["style","avoid"] 只输出指定节。
        """
        records = self.get_preferences(owner_id, agent_id=agent_id, sections=None)
        if not records:
            return ""

        # 检查是否分节模式
        has_sections = any(r.key != "USER.md" for r in records)
        if has_sections and sections is not None:
            return sectioned_format(records, sections=sections)
        if has_sections:
            return sectioned_format(records, sections=None)

        # 兼容模式：旧格式，直接返回原文
        return records[0].value
