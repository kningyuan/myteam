"""Prompt Injections API — CRUD over business/templates/prompt_injections.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

from common.paths import MYTEAM_ROOT

router = APIRouter(prefix="/api/prompt-injections", tags=["prompt-injections"])

INJECTIONS_FILE = MYTEAM_ROOT / "business" / "templates" / "prompt_injections.yaml"


def _load_yaml() -> dict:
    """Load the prompt injections YAML file."""
    if not INJECTIONS_FILE.exists():
        return {"version": "1.1", "injections": {}}
    try:
        import yaml
    except ImportError:
        return {"version": "1.1", "injections": {}}
    text = INJECTIONS_FILE.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return {"version": "1.1", "injections": {}}
    return data


def _save_yaml(data: dict) -> None:
    """Persist the prompt injections YAML file."""
    INJECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
    except ImportError:
        raise HTTPException(status_code=500, detail="YAML 库不可用")
    with open(INJECTIONS_FILE, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


@router.get("/")
def list_injections():
    """List all injection blocks grouped by section."""
    data = _load_yaml()
    injections = data.get("injections") or {}
    result = {}
    for section_id, section_val in injections.items():
        if isinstance(section_val, dict):
            result[section_id] = section_val
        else:
            result[section_id] = {"blocks": [str(section_val)]}
    return {"injections": result, "count": len(result)}


@router.get("/{injection_id}")
def get_injection(injection_id: str):
    """Get a specific injection block."""
    data = _load_yaml()
    injections = data.get("injections") or {}
    if injection_id not in injections:
        raise HTTPException(status_code=404, detail=f"注入块不存在：{injection_id}")
    val = injections[injection_id]
    if isinstance(val, dict):
        content = val
    else:
        content = {"blocks": [str(val)]}
    return {"id": injection_id, "content": content}


@router.post("/")
def create_injection(body: dict):
    """Create a new injection block."""
    injection_id = (body.get("id") or "").strip()
    if not injection_id:
        raise HTTPException(status_code=400, detail="注入 ID 不能为空")
    if "." in injection_id or "/" in injection_id:
        raise HTTPException(status_code=400, detail="注入 ID 不能包含 . 或 /")

    data = _load_yaml()
    injections = data.get("injections") or {}

    if injection_id in injections:
        raise HTTPException(status_code=409, detail=f"注入已存在：{injection_id}")

    content = body.get("content", {})
    injections[injection_id] = content
    data["injections"] = injections
    _save_yaml(data)
    return {"success": True, "id": injection_id}


@router.put("/{injection_id}")
def update_injection(injection_id: str, body: dict):
    """Update an existing injection block."""
    data = _load_yaml()
    injections = data.get("injections") or {}

    if injection_id not in injections:
        raise HTTPException(status_code=404, detail=f"注入不存在：{injection_id}")

    content = body.get("content")
    if content is not None:
        injections[injection_id] = content
        data["injections"] = injections
        _save_yaml(data)
    return {"success": True, "id": injection_id}


@router.delete("/{injection_id}")
def delete_injection(injection_id: str):
    """Delete an injection block."""
    data = _load_yaml()
    injections = data.get("injections") or {}

    if injection_id not in injections:
        raise HTTPException(status_code=404, detail=f"注入不存在：{injection_id}")

    del injections[injection_id]
    data["injections"] = injections
    _save_yaml(data)
    return {"success": True, "id": injection_id}
