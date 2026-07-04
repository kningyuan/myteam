"""Delivery Profiles 管理 API（CRUD over business/templates/delivery_profiles.yaml）。"""

from __future__ import annotations

import yaml
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/delivery-profiles", tags=["delivery-profiles"])


def _load_profiles_file() -> dict:
    from common.paths import delivery_profiles_file

    fp = delivery_profiles_file()
    if not fp.exists():
        return {"profiles": {}}
    try:
        with open(fp, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"profiles": {}}


def _save_profiles_file(data: dict) -> None:
    from common.paths import delivery_profiles_file

    fp = delivery_profiles_file()
    fp.parent.mkdir(parents=True, exist_ok=True)
    with open(fp, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _validate_profile_id(profile_id: str) -> str:
    import re

    tid = (profile_id or "").strip()
    if not tid:
        raise ValueError("profile_id 不能为空")
    if not re.match(r"^[\w][\w-]*$", tid, re.UNICODE):
        raise ValueError(f"profile_id「{tid}」格式非法：小写字母/数字/连字符/下划线")
    return tid


@router.get("/")
def list_profiles():
    """列出所有 delivery profiles。"""
    from common.delivery.delivery_profiles import invalidate_delivery_profiles_cache

    invalidate_delivery_profiles_cache()
    raw = _load_profiles_file()
    profiles = raw.get("profiles") or {}
    out = []
    for pid, cfg in profiles.items():
        if not isinstance(cfg, dict):
            continue
        out.append({
            "id": str(pid),
            "name": str(cfg.get("name") or pid),
            "description": str(cfg.get("description") or "").strip(),
            "process_artifacts": [
                str(x) for x in (cfg.get("process_artifacts") or []) if str(x).strip()
            ],
            "process_checks": cfg.get("process_checks") or {},
            "scaffold": str(cfg.get("scaffold") or "").strip(),
        })
    return {"profiles": out}


@router.post("/")
def create_profile(body: dict):
    """创建新的 delivery profile。"""

    try:
        pid = _validate_profile_id(body.get("id", ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    raw = _load_profiles_file()
    if pid in raw.get("profiles", {}):
        raise HTTPException(status_code=409, detail=f"Profile「{pid}」已存在")

    name = str(body.get("name") or pid).strip()
    description = str(body.get("description") or "").strip()
    artifacts = body.get("process_artifacts") or body.get("artifacts") or []
    if isinstance(artifacts, str):
        artifacts = [x.strip() for x in artifacts.replace("，", ",").split(",") if x.strip()]
    artifacts = [str(a).strip() for a in artifacts if a]
    checks = body.get("process_checks") or {}
    scaffold = str(body.get("scaffold") or "").strip()

    if "profiles" not in raw:
        raw["profiles"] = {}
    raw["profiles"][pid] = {
        "name": name,
        "description": description,
        "process_artifacts": artifacts,
        "process_checks": checks if isinstance(checks, dict) else {},
        "scaffold": scaffold,
    }
    _save_profiles_file(raw)
    return {"success": True, "profile": raw["profiles"][pid]}


@router.put("/{profile_id}")
def update_profile(profile_id: str, body: dict):
    """更新已有 delivery profile。"""
    try:
        pid = _validate_profile_id(profile_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    raw = _load_profiles_file()
    profiles = raw.get("profiles") or {}
    if pid not in profiles:
        raise HTTPException(status_code=404, detail=f"Profile「{pid}」不存在")

    name = str(body.get("name") or profiles[pid].get("name", pid)).strip()
    description = str(body.get("description") or "").strip()
    artifacts = body.get("process_artifacts") or body.get("artifacts") or []
    if isinstance(artifacts, str):
        artifacts = [x.strip() for x in artifacts.replace("，", ",").split(",") if x.strip()]
    artifacts = [str(a).strip() for a in artifacts if a]
    checks = body.get("process_checks") or profiles[pid].get("process_checks", {})
    scaffold = str(body.get("scaffold") or "").strip()

    profiles[pid] = {
        "name": name,
        "description": description,
        "process_artifacts": artifacts,
        "process_checks": checks if isinstance(checks, dict) else {},
        "scaffold": scaffold,
    }
    raw["profiles"] = profiles
    _save_profiles_file(raw)
    return {"success": True, "profile": profiles[pid]}


@router.delete("/{profile_id}")
def delete_profile(profile_id: str):
    """删除 delivery profile。"""
    try:
        pid = _validate_profile_id(profile_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from common.delivery.delivery_profiles import invalidate_delivery_profiles_cache

    raw = _load_profiles_file()
    profiles = raw.get("profiles") or {}
    if pid not in profiles:
        raise HTTPException(status_code=404, detail=f"Profile「{pid}」不存在")
    del profiles[pid]
    raw["profiles"] = profiles
    _save_profiles_file(raw)
    invalidate_delivery_profiles_cache()
    return {"success": True}
