#!/usr/bin/env python3
"""交付模板 CRUD — business/delivery_templates/*.yaml（Hub 管理 Tab）。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import yaml

from common.delivery.delivery_templates import (
    DeliveryTemplateError,
    _parse_template_file,
    delivery_templates_dir,
    invalidate_delivery_templates_cache,
    list_delivery_template_ids,
    load_delivery_template,
)
from common.observability.hub_operation_meta import attach_operated_at, sort_by_operated_at
from common.paths import BUSINESS_DIR

_TEMPLATE_ID_RE = re.compile(r"^[\w][\w-]*$", re.UNICODE)


def validate_template_id(template_id: str) -> str:
    tid = (template_id or "").strip()
    if not tid:
        raise ValueError("template_id 不能为空")
    if not _TEMPLATE_ID_RE.match(tid):
        raise ValueError(f"template_id「{tid}」格式非法：小写字母/数字/连字符")
    if tid.startswith("_"):
        raise ValueError("template_id 不能以 _ 开头")
    return tid


def _template_path(template_id: str) -> Path:
    return delivery_templates_dir() / f"{template_id}.yaml"


def read_template_raw(template_id: str) -> dict[str, Any]:
    """读取模板 YAML 原文。"""
    tpl = load_delivery_template(template_id)
    fp = Path(tpl.source_path)
    if not fp.is_file():
        fp = delivery_templates_dir() / f"{tpl.id}.yaml"
    if not fp.is_file():
        raise FileNotFoundError(f"未找到交付模板「{template_id}」")
    raw = yaml.safe_load(fp.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise DeliveryTemplateError(f"模板格式无效：{fp}")
    return raw


def format_template_api(
    tpl,
    raw: Optional[dict[str, Any]] = None,
    *,
    used_by_workflows: Optional[list[str]] = None,
) -> dict[str, Any]:
    sections = [
        s.get("name", "")
        for s in (tpl.deliverable_template.get("sections") or [])
        if isinstance(s, dict) and s.get("name")
    ]
    raw = raw or {}
    task_types = raw.get("task_types") or getattr(tpl, "task_types", None) or []
    if not isinstance(task_types, list):
        task_types = []
    wf_refs = used_by_workflows if used_by_workflows is not None else workflows_using_template(tpl.id)
    return {
        "id": tpl.id,
        "display_name": tpl.display_name or tpl.id,
        "description": tpl.description,
        "version": tpl.version,
        "section_count": len(sections),
        "sections": sections[:12],
        "task_types": [str(x).strip() for x in task_types if str(x).strip()],
        "default_for": str(raw.get("default_for") or "").strip(),
        "used_by_workflows": wf_refs,
        "can_delete": not wf_refs,
    }


def build_template_workflow_index() -> dict[str, list[str]]:
    """template_id → 引用它的 workflow id 列表。"""
    index: dict[str, list[str]] = {}
    wf_dir = BUSINESS_DIR / "workflows"
    if not wf_dir.is_dir():
        return index
    for fp in wf_dir.glob("*.yaml"):
        try:
            raw = yaml.safe_load(fp.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(raw, dict):
            continue
        wid = str(raw.get("id") or fp.stem)
        ids: set[str] = set()
        for t in raw.get("tasks") or []:
            if isinstance(t, dict) and t.get("template_id"):
                ids.add(str(t["template_id"]).strip())
        for lp in raw.get("loops") or []:
            for bt in (lp.get("body") or []):
                if isinstance(bt, dict) and bt.get("template_id"):
                    ids.add(str(bt["template_id"]).strip())
        for tid in ids:
            if tid:
                index.setdefault(tid, []).append(wid)
    for tid in index:
        index[tid] = sorted(set(index[tid]))
    return index


def _prune_orphan_template_meta(valid_ids: set[str]) -> None:
    """Hub meta 里已无 YAML 的 template_id 清掉，避免列表与磁盘不一致。"""
    from common.observability.hub_operation_meta import map_for_kind, remove

    for tid in map_for_kind("delivery_template"):
        if tid not in valid_ids:
            remove("delivery_template", tid)


def list_templates_for_api() -> list[dict[str, Any]]:
    invalidate_delivery_templates_cache()
    wf_index = build_template_workflow_index()
    items = []
    valid_ids: set[str] = set()
    for tid in list_delivery_template_ids():
        try:
            tpl = load_delivery_template(tid)
        except (OSError, DeliveryTemplateError):
            continue
        fp = Path(tpl.source_path) if tpl.source_path else _template_path(tid)
        if not fp.is_file():
            fp = _template_path(tid)
        if not fp.is_file():
            continue
        valid_ids.add(tid)
        raw: dict[str, Any] = {}
        try:
            raw = read_template_raw(tid)
        except (OSError, ValueError, FileNotFoundError, DeliveryTemplateError):
            raw = {}
        items.append(format_template_api(tpl, raw, used_by_workflows=wf_index.get(tid, [])))
    _prune_orphan_template_meta(valid_ids)
    items = attach_operated_at(items, "delivery_template")
    return sort_by_operated_at(items)


def workflows_using_template(template_id: str) -> list[str]:
    tid = validate_template_id(template_id)
    return build_template_workflow_index().get(tid, [])


def _normalize_body(body: dict[str, Any], *, template_id: str) -> dict[str, Any]:
    tid = validate_template_id(template_id)
    raw: dict[str, Any] = {
        "id": tid,
        "version": str(body.get("version") or "1.0"),
        "display_name": str(body.get("display_name") or tid).strip(),
        "description": str(body.get("description") or "").strip(),
    }
    task_types = body.get("task_types") or []
    if isinstance(task_types, str):
        task_types = [x.strip() for x in task_types.replace("，", ",").split(",") if x.strip()]
    if task_types:
        raw["task_types"] = sorted({str(x).strip() for x in task_types if str(x).strip()})
    default_for = str(body.get("default_for") or "").strip()
    if default_for:
        raw["default_for"] = default_for
    if isinstance(body.get("deliverable_template"), dict):
        raw["deliverable_template"] = body["deliverable_template"]
    if isinstance(body.get("check_rules"), dict):
        raw["check_rules"] = body["check_rules"]
    criteria = body.get("acceptance_criteria")
    if isinstance(criteria, list):
        raw["acceptance_criteria"] = [str(x) for x in criteria if str(x).strip()]
    elif isinstance(body.get("yaml"), str) and body["yaml"].strip():
        parsed = yaml.safe_load(body["yaml"])
        if isinstance(parsed, dict):
            return _normalize_body({**parsed, "id": tid}, template_id=tid)
    if "deliverable_template" not in raw:
        sections = body.get("required_sections") or body.get("sections") or ["正文"]
        if isinstance(sections, str):
            names = [s.strip() for s in sections.replace("，", ",").split(",") if s.strip()]
        else:
            names = [str(s).strip() for s in sections if str(s).strip()]
        raw["deliverable_template"] = {
            "required_heading_level": 2,
            "sections": [
                {"name": n, "description": f"填写「{n}」", "required": True}
                for n in (names or ["正文"])
            ],
        }
    if "check_rules" not in raw:
        secs = [
            s.get("name", "")
            for s in (raw["deliverable_template"].get("sections") or [])
            if isinstance(s, dict) and s.get("name")
        ]
        raw["check_rules"] = {"required_sections": secs, "min_length": 200}
    return raw


def save_template(template_id: str, body: dict[str, Any], *, update: bool = False) -> dict[str, Any]:
    from common.gate.registry import get_spec

    if isinstance(body.get("yaml"), str) and body["yaml"].strip():
        parsed = yaml.safe_load(body["yaml"])
        if isinstance(parsed, dict):
            template_id = validate_template_id(str(parsed.get("id") or template_id))
            body = dict(parsed)
    tid = validate_template_id(template_id)
    data = _normalize_body(body, template_id=tid)
    for tt in data.get("task_types") or []:
        if get_spec(tt) is None:
            raise ValueError(f"task_type「{tt}」未注册，请先在「任务类型」中创建")
    df = str(data.get("default_for") or "").strip()
    if df and df not in (data.get("task_types") or []):
        raise ValueError(f"default_for「{df}」须在 task_types 列表中")
    fp = _template_path(tid)
    if update:
        try:
            existing = load_delivery_template(tid)
            src = Path(existing.source_path)
            if src.is_file():
                fp = src
        except (OSError, DeliveryTemplateError):
            pass
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    invalidate_delivery_templates_cache()
    tpl = load_delivery_template(tid)
    return format_template_api(tpl, data)


def delete_template(template_id: str) -> None:
    invalidate_delivery_templates_cache()
    tid = validate_template_id(template_id)
    refs = workflows_using_template(tid)
    if refs:
        raise ValueError(
            f"模板「{tid}」仍被 Workflow 引用：{', '.join(refs)}。"
            f"请先在「流程」编辑页取消各任务的交付模板绑定，或改选其它 template_id 后再删除",
        )
    tpl = load_delivery_template(tid)
    fp = _template_path(tid)
    if not fp.is_file():
        fp = Path(tpl.source_path)
    if not fp.is_file():
        raise FileNotFoundError(f"未找到交付模板「{tid}」")
    fp.unlink()
    invalidate_delivery_templates_cache()
