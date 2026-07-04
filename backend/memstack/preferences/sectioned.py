#!/usr/bin/env python3
"""偏好分节解析 — 从 USER.md 中提取分节数据并以节级注入。"""
from __future__ import annotations

import re
from typing import Optional

from common.paths import MYTEAM_ROOT
from memstack.preferences.protocol import PreferenceRecord

_SECTION_HEADER_RE = re.compile(r"^##\s+(\S+)", re.MULTILINE)

_DEFAULT_SECTIONS_YAML = MYTEAM_ROOT / "business" / "config" / "preference_sections.yaml"


def _load_section_keys() -> list[str]:
    """从配置文件中读取已注册的 section key 列表。"""
    path = _DEFAULT_SECTIONS_YAML
    if not path.is_file():
        return []
    try:
        import yaml
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "sections" in data:
            return list(data["sections"].keys())
    except Exception:
        pass
    return []


def parse_sections(text: str) -> dict[str, str]:
    """将 USER.md 文本解析为 ```{section_name: content}``` 字典。

    格式：
        ## style
        偏好内容

        ## avoid
        禁忌内容

    返回：有序字典，保持文件中 section 出现顺序。
    不含 ## 的部分作为 ``_header`` 存入。
    """
    if not text or not text.strip():
        return {}
    sections: dict[str, str] = {}
    parts = _SECTION_HEADER_RE.split(text)
    # parts 格式: [header_text, section1, content1, section2, content2, ...]
    if len(parts) >= 3:
        header = parts[0].strip()
        if header:
            sections["_header"] = header
        for i in range(1, len(parts) - 1, 2):
            key = parts[i].strip().lower()
            content = parts[i + 1].strip()
            if key and content:
                sections[key] = content
    else:
        text_only = parts[0].strip()
        if text_only:
            sections["_header"] = text_only
    return sections


def to_records(
    text: str,
    owner_id: str = "default",
    *,
    agent_id: str = "",
) -> list[PreferenceRecord]:
    """将 USER.md 文本解析为分节 PreferenceRecord 列表。

    支持两种模式：
    1. 分节模式：每个 ## section 对应一个 key=section_name 的 record
    2. 兼容模式：无 ## 的旧格式 → 一个 key=USER.md 的 record（向后兼容）
    """
    sections = parse_sections(text)
    if not sections:
        return []
    records: list[PreferenceRecord] = []
    _load_section_keys()

    for key, content in sections.items():
        if key == "_header":
            continue
        # 如果 section 不在已注册列表中但内容非空，仍保留（向前适应）
        records.append(
            PreferenceRecord(
                owner_id=owner_id,
                key=key,
                value=content,
                source="static",
            )
        )

    # 兼容：如果没有任何 ## 分节，回退旧格式
    if not records:
        records.append(
            PreferenceRecord(
                owner_id=owner_id,
                key="USER.md",
                value=text.strip(),
                source="static",
            )
        )
    return records


def filter_records(
    records: list[PreferenceRecord],
    sections: Optional[list[str]] = None,
) -> list[PreferenceRecord]:
    """按 section 过滤记录。sections=None 返回全部。"""
    if sections is None:
        return records
    section_set = {s.strip().lower() for s in sections}
    return [r for r in records if r.key.strip().lower() in section_set]


def format_block(
    records: list[PreferenceRecord],
    sections: Optional[list[str]] = None,
) -> str:
    """将 records 格式化为可注入 prompt 的块。

    示例输出：
        【风格偏好】
        - 偏好简洁的代码风格
        - 优先使用类型注解

        【禁忌】
        - 不要在单测中使用 mock
    """
    filtered = filter_records(records, sections)
    if not filtered:
        return ""
    lines: list[str] = []
    for r in filtered:
        section_name = r.key.replace("_", " ").title()
        lines.append(f"【{section_name}】")
        for line in r.value.split("\n"):
            line = line.strip()
            if line:
                if not line.startswith("-"):
                    line = f"- {line}"
                lines.append(line)
        lines.append("")
    return "\n".join(lines).strip()
