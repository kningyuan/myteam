#!/usr/bin/env python3
"""Workflow 协作配置 — options.collaboration 为真源，skill_config 为 fallback。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class CollaborationConfig:
    project_group_enabled: bool
    include_main: bool
    notifications_enabled: bool
    group_discussion_enabled: bool
    loop_discussion_profile: str
    name_prefix: str = ""


def _normalized_collaboration(options: dict[str, Any]) -> dict[str, Any]:
    """合并 options.collaboration 与旧版扁平字段。"""
    opts = dict(options or {})
    collab: dict[str, Any] = dict(opts.get("collaboration") or {})

    pg = dict(collab.get("project_group") or {})
    notif = dict(collab.get("notifications") or {})
    gd = dict(collab.get("group_discussion") or {})

    if "group_discussion_enabled" in opts and "enabled" not in gd:
        gd["enabled"] = bool(opts["group_discussion_enabled"])
    if opts.get("loop_discussion_profile") and "profile" not in gd:
        gd["profile"] = str(opts["loop_discussion_profile"]).strip()

    collab["project_group"] = pg
    collab["notifications"] = notif
    collab["group_discussion"] = gd
    return collab


def collaboration_from_options(options: dict[str, Any] | None) -> CollaborationConfig:
    """从 workflow options 解析协作配置（无 project 上下文）。"""
    from common.skill_settings import is_auto_group_enabled, is_project_group_enabled

    try:
        from store.skill_config import skill_config
    except ImportError:
        skill_config = None  # type: ignore

    opts = dict(options or {})
    collab = _normalized_collaboration(opts)
    pg = collab.get("project_group") or {}
    notif = collab.get("notifications") or {}
    gd = collab.get("group_discussion") or {}

    if "enabled" in pg:
        pg_enabled = bool(pg["enabled"])
    else:
        pg_enabled = is_auto_group_enabled()

    if "enabled" in notif:
        notif_enabled = bool(notif["enabled"])
    else:
        notif_enabled = is_project_group_enabled()

    if "enabled" in gd:
        gd_enabled = bool(gd["enabled"])
    else:
        gd_enabled = bool(opts.get("group_discussion_enabled"))

    profile = str(gd.get("profile") or opts.get("loop_discussion_profile") or "").strip()

    if "include_main" in pg:
        include_main = bool(pg["include_main"])
    elif skill_config is not None:
        include_main = bool(skill_config.get("auto_group", "include_main", default=True))
    else:
        include_main = True

    if "name_prefix" in pg:
        name_prefix = str(pg.get("name_prefix") or "")
    elif skill_config is not None:
        name_prefix = str(skill_config.get("auto_group", "name_prefix", default="") or "")
    else:
        name_prefix = ""

    return CollaborationConfig(
        project_group_enabled=pg_enabled,
        include_main=include_main,
        notifications_enabled=notif_enabled,
        group_discussion_enabled=gd_enabled,
        loop_discussion_profile=profile,
        name_prefix=name_prefix,
    )


def collaboration_for_project(project_id: str) -> CollaborationConfig:
    """按项目 meta.workflow 加载协作配置；无 workflow 时退回 skill_config。"""
    try:
        from common.store import Store
        from common.workflow_loader import load_workflow

        store = Store()
        try:
            proj = store.get_project(project_id) or {}
            wf_id = (proj.get("meta") or {}).get("workflow")
            if wf_id:
                return collaboration_from_options(load_workflow(wf_id).options)
        finally:
            store.close()
    except Exception:
        pass
    return collaboration_from_options({})


def project_group_enabled(project_id: Optional[str] = None) -> bool:
    if project_id:
        return collaboration_for_project(project_id).project_group_enabled
    return collaboration_from_options({}).project_group_enabled


def notifications_enabled(project_id: str) -> bool:
    return collaboration_for_project(project_id).notifications_enabled


def group_discussion_enabled(project_id: str) -> bool:
    return collaboration_for_project(project_id).group_discussion_enabled


def loop_discussion_profile_id(project_id: str) -> str:
    return collaboration_for_project(project_id).loop_discussion_profile
