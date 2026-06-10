#!/usr/bin/env python3
"""按 task_type / interaction kind 渲染标准 Prompt（Strategy Registry）。

任务 description 只承载变量（对象、视角、范围）；通用约束由 prompt_templates.yaml 统一提供。
与 agent 身份解耦：同一 research 模板可用于 product / research / developer 等任意执行者。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from common.paths import prompt_templates_file


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def render_template(template: str, variables: dict[str, Any]) -> str:
    """简单占位符替换（避免 str.format 与 JSON 花括号冲突）。"""
    out = template or ""
    for key, val in variables.items():
        out = out.replace("{" + key + "}", str(val) if val is not None else "")
    return out.strip()


@lru_cache(maxsize=1)
def _load_prompt_registry(path_str: str) -> dict:
    raw = _load_yaml(Path(path_str))
    return {
        "kinds": raw.get("kinds") if isinstance(raw.get("kinds"), dict) else {},
        "task_types": raw.get("task_types") if isinstance(raw.get("task_types"), dict) else {},
    }


def load_prompt_registry(path: Optional[Path] = None) -> dict:
    return _load_prompt_registry(str(path or prompt_templates_file()))


def get_kind_prompt(kind: str, path: Optional[Path] = None) -> Optional[str]:
    reg = load_prompt_registry(path)
    tpl = reg.get("kinds", {}).get(kind)
    return tpl if isinstance(tpl, str) and tpl.strip() else None


def get_task_type_prompt(task_type: str, interaction_kind: str = "execute",
                         path: Optional[Path] = None) -> Optional[str]:
    reg = load_prompt_registry(path)
    types = reg.get("task_types", {})
    cfg = types.get(task_type) if isinstance(types.get(task_type), dict) else None
    if cfg:
        tpl = cfg.get(interaction_kind)
        if isinstance(tpl, str) and tpl.strip():
            return tpl
    default = types.get("_default")
    if isinstance(default, dict):
        tpl = default.get(interaction_kind)
        if isinstance(tpl, str) and tpl.strip():
            return tpl
    return None


def render_kind_intent(kind: str, variables: dict[str, Any],
                       path: Optional[Path] = None) -> str:
    tpl = get_kind_prompt(kind, path)
    if not tpl:
        return str(variables.get("fallback") or "")
    return render_template(tpl, variables)


def render_execute_intent(task: dict, path: Optional[Path] = None) -> str:
    """把 task.description 嵌入 task_type 标准 execute 模板。"""
    from common.registry import TASK_TYPE_DISPLAY_NAMES, get_spec

    task_type = (task.get("task_type") or "").strip()
    desc = (task.get("description") or task.get("name") or "").strip()
    spec = get_spec(task_type) if task_type else None
    tpl = get_task_type_prompt(task_type, "execute", path)
    if not tpl:
        return desc
    sections = ""
    if spec and spec.required_sections:
        sections = "、".join(spec.required_sections)
    return render_template(tpl, {
        "task_description": desc,
        "task_name": task.get("name") or task.get("id") or "",
        "task_id": task.get("id") or "",
        "task_type": task_type,
        "task_type_label": (spec.display_name if spec else "") or TASK_TYPE_DISPLAY_NAMES.get(
            task_type, task_type,
        ),
        "outcome_kind": spec.outcome_kind if spec else "artifact",
        "required_sections": sections,
    })
