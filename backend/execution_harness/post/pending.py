#!/usr/bin/env python3
"""Skill review 待审批目录 _pending/。"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from execution_harness.config import PENDING_SKILLS_DIR, skills_write_approval

import shutil

from common.skill_catalog import SKILLS_DIR

__all__ = [
    "PENDING_SKILLS_DIR",
    "approve_pending",
    "create_pending_bundle",
    "get_pending",
    "list_pending",
    "reject_pending",
]


def pending_dir(pending_id: Optional[str] = None) -> Path:
    base = PENDING_SKILLS_DIR
    base.mkdir(parents=True, exist_ok=True)
    if pending_id:
        return base / pending_id
    return base


def create_pending_bundle(
    *,
    project_id: str,
    task_id: str,
    task_type: str,
    agent_id: str,
    action: str,
    skill_id: str = "",
    notes: str = "",
    content: str = "",
) -> str:
    """创建 pending 包；返回 pending_id。"""
    pid = uuid.uuid4().hex[:12]
    d = pending_dir(pid)
    d.mkdir(parents=True, exist_ok=True)
    meta = {
        "pending_id": pid,
        "project_id": project_id,
        "task_id": task_id,
        "task_type": task_type,
        "agent_id": agent_id,
        "action": action,
        "skill_id": skill_id,
        "notes": notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "write_approval": skills_write_approval(),
    }
    (d / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if content.strip():
        (d / "SKILL.patch.md").write_text(content.strip() + "\n", encoding="utf-8")
    return pid


def list_pending() -> list[dict]:
    base = pending_dir()
    out: list[dict] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        meta = _read_pending_meta(child)
        if meta:
            out.append(meta)
    return out


def _read_pending_meta(d: Path) -> dict | None:
    meta_path = d / "meta.json"
    if not meta_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["path"] = str(d)
        patch = d / "SKILL.patch.md"
        meta["has_patch"] = patch.is_file()
        if patch.is_file():
            meta["patch_preview"] = patch.read_text(encoding="utf-8", errors="replace")[:400]
        return meta
    except (json.JSONDecodeError, OSError):
        return None


def get_pending(pending_id: str) -> dict | None:
    d = pending_dir(pending_id)
    if not d.is_dir():
        return None
    meta = _read_pending_meta(d)
    if not meta:
        return None
    patch = d / "SKILL.patch.md"
    if patch.is_file():
        meta["patch_content"] = patch.read_text(encoding="utf-8", errors="replace")
    return meta


def approve_pending(pending_id: str) -> dict:
    """批准 pending：将 patch 追加到目标 Skill 的 SKILL.md。"""
    d = pending_dir(pending_id)
    meta = get_pending(pending_id)
    if not meta:
        return {"success": False, "error": "pending 不存在"}
    skill_id = (meta.get("skill_id") or "").strip()
    if not skill_id:
        return {"success": False, "error": "缺少 skill_id"}
    patch_path = d / "SKILL.patch.md"
    if not patch_path.is_file():
        return {"success": False, "error": "缺少 SKILL.patch.md"}
    patch = patch_path.read_text(encoding="utf-8", errors="replace").strip()
    if not patch:
        return {"success": False, "error": "patch 为空"}
    action = (meta.get("action") or "patch").strip().lower()
    skill_dir = SKILLS_DIR / skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    if action == "reference":
        ref_dir = skill_dir / "references"
        ref_dir.mkdir(parents=True, exist_ok=True)
        safe_tid = re.sub(r"[^\w\-]+", "_", meta.get("task_id") or pending_id)
        out = ref_dir / f"pending-{safe_tid}.md"
        out.write_text(patch + "\n", encoding="utf-8")
        applied = str(out)
    else:
        skill_md = skill_dir / "SKILL.md"
        existing = skill_md.read_text(encoding="utf-8", errors="replace") if skill_md.is_file() else ""
        sep = "\n\n" if existing.strip() else ""
        skill_md.write_text(existing.rstrip() + sep + patch + "\n", encoding="utf-8")
        applied = str(skill_md)
    shutil.rmtree(d, ignore_errors=True)
    return {
        "success": True,
        "pending_id": pending_id,
        "skill_id": skill_id,
        "action": action,
        "applied_path": applied,
    }


def reject_pending(pending_id: str) -> dict:
    d = pending_dir(pending_id)
    if not d.is_dir():
        return {"success": False, "error": "pending 不存在"}
    shutil.rmtree(d, ignore_errors=True)
    return {"success": True, "pending_id": pending_id}
