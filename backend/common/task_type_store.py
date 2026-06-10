#!/usr/bin/env python3
"""任务类型注册表读写 — templates.yaml 的 CRUD 入口（Strategy Registry 层）。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

import yaml

from common import paths
from common.paths import templates_file
from common.registry import invalidate_registry_cache, load_registry

_TASK_TYPE_ID_RE = re.compile(r"^[\w][\w-]*$", re.UNICODE)


def _load_raw(path: Optional[Path] = None) -> dict[str, Any]:
    fp = path or templates_file()
    if not fp.is_file():
        return {}
    raw = yaml.safe_load(fp.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _save_raw(data: dict[str, Any], path: Optional[Path] = None) -> None:
    fp = path or templates_file()
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    invalidate_registry_cache()


def validate_task_type_id(task_type: str) -> str:
    tid = (task_type or "").strip()
    if not tid:
        raise ValueError("task_type 不能为空")
    if not _TASK_TYPE_ID_RE.match(tid):
        raise ValueError(
            f"task_type「{tid}」格式非法：请用小写字母/数字/连字符，如 research、my-task")
    return tid


def _default_config(*, display_name: str, sections: Optional[list[str]] = None) -> dict[str, Any]:
    names = [s.strip() for s in (sections or ["正文"]) if s and s.strip()] or ["正文"]
    return {
        "display_name": display_name or "未命名类型",
        "deliverable_template": {
            "required_heading_level": 2,
            "sections": [
                {"name": n, "description": f"填写「{n}」章节", "required": True}
                for n in names
            ],
        },
        "check_rules": {
            "required_sections": names,
            "min_length": 200,
        },
    }


def list_task_type_ids() -> list[str]:
    return sorted(load_registry().keys())


def get_task_type_raw(task_type: str, path: Optional[Path] = None) -> Optional[dict[str, Any]]:
    tid = validate_task_type_id(task_type)
    cfg = _load_raw(path).get(tid)
    return dict(cfg) if isinstance(cfg, dict) else None


def upsert_task_type(
    task_type: str,
    body: dict[str, Any],
    *,
    path: Optional[Path] = None,
) -> dict[str, Any]:
    """创建或更新任务类型；body 为 templates.yaml 中单类型的配置对象。"""
    tid = validate_task_type_id(task_type)
    raw = _load_raw(path)
    existing = raw.get(tid) if isinstance(raw.get(tid), dict) else {}

    display = (body.get("display_name") or existing.get("display_name") or tid).strip()
    sections_in = body.get("required_sections")
    if sections_in is None and body.get("sections"):
        sections_in = [s.get("name") for s in body["sections"] if isinstance(s, dict) and s.get("name")]

    if not existing and not body.get("deliverable_template"):
        cfg = _default_config(display_name=display, sections=sections_in)
        cfg.update({k: v for k, v in body.items() if k not in ("required_sections", "sections")})
    else:
        cfg = dict(existing)
        cfg.update(body)
        if display:
            cfg["display_name"] = display
        if sections_in is not None:
            names = [str(s).strip() for s in sections_in if str(s).strip()]
            dt = dict(cfg.get("deliverable_template") or {})
            dt["required_heading_level"] = int(dt.get("required_heading_level") or 2)
            dt["sections"] = [
                {"name": n, "description": f"填写「{n}」", "required": True}
                for n in (names or ["正文"])
            ]
            cfg["deliverable_template"] = dt
            cr = dict(cfg.get("check_rules") or {})
            cr["required_sections"] = names or ["正文"]
            cr.setdefault("min_length", 200)
            cfg["check_rules"] = cr

    if body.get("outcome_kind") in ("artifact", "action", "code_project"):
        cfg["outcome_kind"] = body["outcome_kind"]

    raw[tid] = cfg
    _save_raw(raw, path)
    return {"task_type": tid, "config": cfg}


def delete_task_type(task_type: str, *, path: Optional[Path] = None) -> None:
    tid = validate_task_type_id(task_type)
    users = agents_using_task_type(tid)
    if users:
        raise ValueError(
            f"无法删除 task_type「{tid}」：仍被 Agent 配置引用：{', '.join(users)}")
    wf_users = workflows_using_task_type(tid)
    if wf_users:
        raise ValueError(
            f"无法删除 task_type「{tid}」：仍被 Workflow 引用：{', '.join(wf_users)}")

    raw = _load_raw(path)
    if tid not in raw:
        raise ValueError(f"task_type「{tid}」不存在")
    del raw[tid]
    _save_raw(raw, path)


def agents_using_task_type(task_type: str) -> list[str]:
    reg_file = paths.AGENTS_REGISTRY_FILE
    if not reg_file.is_file():
        return []
    try:
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out = []
    for aid, meta in (reg.get("agents") or {}).items():
        if task_type in (meta.get("task_types") or []):
            out.append(aid)
    return sorted(out)


def format_task_type_api(spec) -> dict[str, Any]:
    """将 FormatSpec 转为 Hub / 管理 Tab API 结构。"""
    gate_checks = []
    if spec.outcome_kind == "code_project":
        gate_checks.append(f"≥{spec.min_project_files} 个文件")
        if spec.require_code_file:
            gate_checks.append("须含脚本/代码")
        gate_checks.extend(spec.file_exists)
    else:
        gate_checks.extend(spec.required_sections)
        gate_checks.extend(spec.file_exists)
    return {
        "task_type": spec.task_type,
        "display_name": spec.display_name or spec.task_type,
        "outcome_kind": spec.outcome_kind,
        "required_sections": spec.required_sections,
        "must_include": spec.must_include,
        "stub_floor": spec.stub_floor,
        "acceptance_criteria": spec.acceptance_criteria,
        "section_count": len(spec.sections),
        "sections": [
            {"name": s.get("name", ""), "description": s.get("description", "")}
            for s in spec.sections if isinstance(s, dict)
        ],
        "structure": spec.structure,
        "file_exists": spec.file_exists,
        "min_project_files": spec.min_project_files,
        "require_code_file": spec.require_code_file,
        "gate_checks": gate_checks,
    }


def list_task_types_for_api() -> list[dict[str, Any]]:
    return [
        format_task_type_api(spec)
        for _, spec in sorted(load_registry().items(), key=lambda x: x[0])
    ]


def workflows_using_task_type(task_type: str) -> list[str]:
    wf_dir = paths.BUSINESS_DIR / "workflows"
    if not wf_dir.is_dir():
        return []
    hits: list[str] = []
    for fp in wf_dir.glob("*.yaml"):
        try:
            raw = yaml.safe_load(fp.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(raw, dict):
            continue
        for t in raw.get("tasks") or []:
            if isinstance(t, dict) and t.get("task_type") == task_type:
                hits.append(raw.get("id") or fp.stem)
                break
    return sorted(set(hits))
