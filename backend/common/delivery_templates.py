#!/usr/bin/env python3
"""交付模板实例 — business/delivery_templates/*.yaml。

选中 template_id 时，Gate / scaffold / Review 清单以模板 YAML 为准；
delivery_profile / outcome_kind 仍来自 task_type。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

from common.paths import delivery_templates_dir


class DeliveryTemplateError(ValueError):
    pass


@dataclass
class DeliveryTemplate:
    id: str
    version: str = "1.0"
    display_name: str = ""
    description: str = ""
    deliverable_template: dict = field(default_factory=dict)
    check_rules: dict = field(default_factory=dict)
    acceptance_criteria: list[str] = field(default_factory=list)
    task_types: list[str] = field(default_factory=list)
    default_for: str = ""
    source_path: str = ""


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _parse_template_file(path: Path) -> DeliveryTemplate:
    raw = _load_yaml(path)
    if not raw:
        raise DeliveryTemplateError(f"模板文件无效或为空：{path}")
    tid = str(raw.get("id") or path.stem).strip()
    if not tid:
        raise DeliveryTemplateError(f"模板缺少 id：{path}")
    criteria = raw.get("acceptance_criteria")
    if not isinstance(criteria, list):
        criteria = []
    task_types = raw.get("task_types") or []
    if not isinstance(task_types, list):
        task_types = []
    return DeliveryTemplate(
        id=tid,
        version=str(raw.get("version", "1.0")),
        display_name=str(raw.get("display_name") or tid).strip(),
        description=str(raw.get("description") or "").strip(),
        deliverable_template=dict(raw.get("deliverable_template") or {}),
        check_rules=dict(raw.get("check_rules") or {}),
        acceptance_criteria=[str(x) for x in criteria if str(x).strip()],
        task_types=[str(x).strip() for x in task_types if str(x).strip()],
        default_for=str(raw.get("default_for") or "").strip(),
        source_path=str(path),
    )


@lru_cache(maxsize=1)
def _scan_template_index(root_str: str) -> dict[str, str]:
    """template_id → 文件路径（business/delivery_templates/*.yaml）。"""
    root = Path(root_str)
    index: dict[str, str] = {}
    if not root.is_dir():
        return index
    for fp in sorted(root.glob("*.yaml")):
        try:
            tpl = _parse_template_file(fp)
            index[tpl.id] = str(fp)
        except DeliveryTemplateError:
            continue
    return index


def invalidate_delivery_templates_cache() -> None:
    _scan_template_index.cache_clear()
    _load_delivery_template_cached.cache_clear()


def list_delivery_template_ids() -> list[str]:
    return sorted(_scan_template_index(str(delivery_templates_dir())).keys())


def load_delivery_template(template_id: str) -> DeliveryTemplate:
    tid = (template_id or "").strip()
    if not tid:
        raise DeliveryTemplateError("template_id 为空")
    tpl = _load_delivery_template_cached(str(delivery_templates_dir()), tid)
    if tpl is None:
        available = ", ".join(list_delivery_template_ids()) or "（无）"
        raise DeliveryTemplateError(
            f"未找到交付模板「{tid}」。可用：{available}",
        )
    return tpl


@lru_cache(maxsize=128)
def _load_delivery_template_cached(root_str: str, template_id: str) -> Optional[DeliveryTemplate]:
    index = _scan_template_index(root_str)
    path = index.get(template_id)
    if not path:
        return None
    fp = Path(path)
    if not fp.is_file():
        return None
    return _parse_template_file(fp)


def validate_template_id(template_id: str) -> None:
    load_delivery_template(template_id)
