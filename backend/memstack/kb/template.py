#!/usr/bin/env python3
"""KB 条目模板 — 按 task_type 定义结构化写入/验证。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from common.paths import MYTEAM_ROOT

_DEFAULT_TEMPLATES_YAML = MYTEAM_ROOT / "business" / "config" / "kb_templates.yaml"
_JSON_MARKER = "_json_struct"


def _load_templates() -> dict[str, Any]:
    """加载 kb_templates.yaml 配置。"""
    path = _DEFAULT_TEMPLATES_YAML
    if not path.is_file():
        return {}
    try:
        import yaml
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "templates" in data:
            return dict(data["templates"])
    except Exception:
        pass
    return {}


def get_template(task_type: str) -> Optional[dict]:
    """按 task_type 获取模板定义。无模板返回 None。"""
    templates = _load_templates()
    return templates.get(task_type)


def list_templated_task_types() -> list[str]:
    """列出所有有模板的 task_type。"""
    return sorted(_load_templates().keys())


def validate_content(task_type: str, content_dict: dict[str, str]) -> list[str]:
    """验证 content_dict 是否满足模板要求。

    返回缺失的必填字段列表（空列表表示验证通过）。
    """
    template = get_template(task_type)
    if template is None:
        return []
    sections = template.get("sections", [])
    missing = []
    for sec in sections:
        if sec.get("required", False):
            key = sec["key"]
            val = content_dict.get(key, "").strip()
            if not val:
                missing.append(key)
    return missing


def content_to_json(content_dict: dict[str, str]) -> str:
    """将结构化 content 序列化为存 JSON。

    添加 _json_struct 标记以区分结构化与非结构化内容。
    """
    data = dict(content_dict)
    data[_JSON_MARKER] = True
    return json.dumps(data, ensure_ascii=False)


def json_to_content(stored: str) -> Optional[dict[str, str]]:
    """将 JSON 反序列化为结构化字典。

    如果不是 JSON 结构或缺少标记，返回 None（自由文本，向后兼容）。
    """
    if not stored.startswith("{"):
        return None
    try:
        data = json.loads(stored)
        if isinstance(data, dict) and data.get(_JSON_MARKER):
            return {k: v for k, v in data.items() if k != _JSON_MARKER}
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def is_structured(stored: str) -> bool:
    """判断存储内容是否为结构化 JSON。"""
    return json_to_content(stored) is not None


def format_kb_entry(task_type: str, content_dict: dict[str, str]) -> str:
    """将结构化 content 格式化为可读文本（用于 inject/prompt 显示）。"""
    template = get_template(task_type)
    lines: list[str] = []
    if template:
        # 按模板顺序输出
        seen = set()
        for sec in template.get("sections", []):
            key = sec["key"]
            val = content_dict.get(key, "").strip()
            if val:
                seen.add(key)
                lines.append(f"{sec['display']}：{val}")
        # 补模板外字段
        for key, val in content_dict.items():
            if key not in seen and val.strip():
                lines.append(f"{key}：{val.strip()}")
    else:
        # 无模板时直接输出
        for key, val in content_dict.items():
            if val.strip():
                lines.append(f"{key}：{val.strip()}")
    return "\n".join(lines)
