"""Prompt Templates API — CRUD over business/templates/prompt_templates.yaml.

读写 Strategy Registry 中的 prompt_templates.yaml（kinds + task_types 两层）。
创建/更新采用"增量合并"策略：POST/PUT 的 body 若包含 kinds 或 task_types 键，
则与现有 YAML 合并后写回。
"""
from __future__ import annotations


from fastapi import APIRouter, HTTPException

from common.paths import MYTEAM_ROOT

router = APIRouter(prefix="/api/prompt-templates", tags=["prompt-templates"])

TEMPLATES_FILE = MYTEAM_ROOT / "business" / "templates" / "prompt_templates.yaml"


def _load_yaml() -> dict:
    """Load the prompt templates YAML file."""
    if not TEMPLATES_FILE.exists():
        return {"version": "1.0", "kinds": {}, "task_types": {}}
    try:
        import yaml
    except ImportError:
        return {"version": "1.0", "kinds": {}, "task_types": {}}
    text = TEMPLATES_FILE.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return {"version": "1.0", "kinds": {}, "task_types": {}}
    return data


def _save_yaml(data: dict) -> None:
    """Persist the prompt templates YAML file."""
    TEMPLATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
    except ImportError:
        raise HTTPException(status_code=500, detail="YAML 库不可用")
    with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge overlay into base (in-place on a copy of base)."""
    result = dict(base)
    for key, val in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def _kind_ids(data: dict) -> list[str]:
    kinds = data.get("kinds")
    if isinstance(kinds, dict):
        return sorted(kinds.keys())
    return []


def _task_type_ids(data: dict) -> list[str]:
    types = data.get("task_types")
    if isinstance(types, dict):
        return sorted(types.keys())
    return []


@router.get("/")
def list_templates(kind: str = ""):
    """List all prompt templates, optionally filtered by kind."""
    data = _load_yaml()
    if kind == "kind" or kind == "kinds" or kind == "":
        result_kinds = {}
        for k, v in (data.get("kinds") or {}).items():
            result_kinds[k] = {"id": k, "content": v if isinstance(v, str) else "", "kind": "kind"}
        if kind and kind not in ("kind", "kinds", ""):
            return {"kinds": result_kinds, "task_types": {}, "count": len(result_kinds)}
        if kind == "kind" or kind == "kinds":
            return {"kinds": result_kinds, "task_types": {}, "count": len(result_kinds)}
    if kind == "task_type" or kind == "task_types" or kind == "":
        result_types = {}
        for k, v in (data.get("task_types") or {}).items():
            if isinstance(v, dict):
                result_types[k] = {"id": k, "content": v, "kind": "task_type"}
            else:
                result_types[k] = {"id": k, "content": str(v), "kind": "task_type"}
        if kind and kind not in ("task_type", "task_types", ""):
            return {"kinds": {}, "task_types": result_types, "count": len(result_types)}
        if kind == "task_type" or kind == "task_types":
            return {"kinds": {}, "task_types": result_types, "count": len(result_types)}
    return {"kinds": result_kinds, "task_types": result_types, "count": len(result_kinds) + len(result_types)}


@router.get("/{template_id}")
def get_template(template_id: str):
    """Get a specific prompt template."""
    data = _load_yaml()
    kinds = data.get("kinds") or {}
    if template_id in kinds:
        content = kinds[template_id]
        return {
            "id": template_id,
            "content": content if isinstance(content, str) else "",
            "kind": "kind",
            "path": "kinds." + template_id,
        }
    types = data.get("task_types") or {}
    if template_id in types:
        val = types[template_id]
        if isinstance(val, dict):
            # Check if it has an execute sub-key
            if "execute" in val:
                return {
                    "id": template_id,
                    "content": val,
                    "kind": "task_type",
                    "path": "task_types." + template_id,
                }
            return {
                "id": template_id,
                "content": val,
                "kind": "task_type",
                "path": "task_types." + template_id,
            }
        return {
            "id": template_id,
            "content": val if isinstance(val, str) else "",
            "kind": "task_type",
            "path": "task_types." + template_id,
        }
    raise HTTPException(status_code=404, detail=f"模板不存在：{template_id}")


@router.post("/")
def create_template(body: dict):
    """Create a new prompt template."""
    template_id = (body.get("id") or "").strip()
    if not template_id:
        raise HTTPException(status_code=400, detail="模板 ID 不能为空")
    if "." in template_id or "/" in template_id:
        raise HTTPException(status_code=400, detail="模板 ID 不能包含 . 或 /")

    data = _load_yaml()
    kinds = data.get("kinds") or {}
    types = data.get("task_types") or {}

    if template_id in kinds or template_id in types:
        raise HTTPException(status_code=409, detail=f"模板已存在：{template_id}")

    kind = body.get("kind", "kind")
    content = body.get("content", "")

    if kind == "kind":
        if "kinds" not in data:
            data["kinds"] = {}
        data["kinds"][template_id] = content
    elif kind == "task_type":
        if "task_types" not in data:
            data["task_types"] = {}
        data["task_types"][template_id] = content
    else:
        # Default to kind
        if "kinds" not in data:
            data["kinds"] = {}
        data["kinds"][template_id] = content

    _save_yaml(data)
    return {"success": True, "id": template_id, "kind": kind}


@router.put("/{template_id}")
def update_template(template_id: str, body: dict):
    """Update an existing prompt template."""
    data = _load_yaml()
    kinds = data.get("kinds") or {}
    types = data.get("task_types") or {}

    body.get("kind")
    content = body.get("content")

    # Update kind-level template
    if template_id in kinds:
        if content is not None:
            kinds[template_id] = content
            data["kinds"] = kinds
        _save_yaml(data)
        return {"success": True, "id": template_id, "kind": "kind"}

    # Update task_type-level template
    if template_id in types:
        if content is not None:
            if isinstance(types[template_id], dict):
                types[template_id].update(content) if isinstance(content, dict) else None
                # If content is a string, replace the whole thing
                if isinstance(content, str):
                    types[template_id] = content
            else:
                types[template_id] = content if isinstance(content, str) else str(content)
            data["task_types"] = types
        _save_yaml(data)
        return {"success": True, "id": template_id, "kind": "task_type"}

    raise HTTPException(status_code=404, detail=f"模板不存在：{template_id}")


@router.delete("/{template_id}")
def delete_template(template_id: str):
    """Delete a prompt template."""
    data = _load_yaml()
    kinds = data.get("kinds") or {}
    types = data.get("task_types") or {}

    if template_id in kinds:
        del kinds[template_id]
        data["kinds"] = kinds
        _save_yaml(data)
        return {"success": True, "id": template_id, "kind": "kind"}

    if template_id in types:
        del types[template_id]
        data["task_types"] = types
        _save_yaml(data)
        return {"success": True, "id": template_id, "kind": "task_type"}

    raise HTTPException(status_code=404, detail=f"模板不存在：{template_id}")
