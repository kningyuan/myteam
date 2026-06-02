"""项目协作群 — team_config 后自动建群、进度通报。"""

from __future__ import annotations

import json
import re
from typing import Optional

from base.group_manager import (
    add_member,
    bind_group_project,
    create_group,
    find_group_by_project,
    remove_member,
    restore_group,
    send_group_message,
    update_group_meta,
)
from hub.paths import PROJECTS_DIR
from hub.services.group_broadcast import publish
from store.skill_config import skill_config


def _resolve_project_display_name(project_id: str, hint: str = "") -> str:
    """群名称 = 项目 human 名称（优先 task_data.project.name）。"""
    name = ""
    try:
        td = PROJECTS_DIR / project_id / "task_data.json"
        if td.is_file():
            data = json.loads(td.read_text(encoding="utf-8"))
            name = (data.get("project") or {}).get("name", "").strip()
    except Exception:
        pass
    if name:
        return name

    hint = (hint or "").strip()
    if hint and hint not in ("test", "Test") and hint != project_id:
        return hint

    if project_id.startswith("pro_"):
        base = project_id[4:]
        base = re.sub(r"_\d{8}$", "", base)
        if base:
            return base.replace("_", " ")
    return project_id


def _group_title(project_id: str, project_name: str = "") -> str:
    display = _resolve_project_display_name(project_id, project_name)
    prefix = (skill_config.get("auto_group", "name_prefix", default="") or "").strip()
    if prefix:
        return f"{prefix}{display}" if prefix.endswith((":", "：", " ")) else f"{prefix}: {display}"
    return display


def setup_project_group(
    project_id: str,
    team: list[str],
    project_name: str = "",
) -> tuple[bool, str, Optional[str]]:
    """为项目创建/同步协作群并绑定 project_id。返回 (ok, message, group_id)。"""
    if not skill_config.get("auto_group", "enabled", default=True):
        return True, "auto_group disabled", None

    members = set(team or [])
    if skill_config.get("auto_group", "include_main", default=True):
        members.add("main")

    display = _resolve_project_display_name(project_id, project_name)
    group_name = _group_title(project_id, project_name)
    group_desc = f"项目协作 · {display}"

    existing = find_group_by_project(project_id)
    if existing:
        group_id = existing["id"]
        if existing.get("status") == "dissolved":
            restore_group(group_id)
        update_group_meta(group_id, name=group_name, description=group_desc)
        current = set(existing.get("members") or [])
        for aid in members - current:
            add_member(group_id, aid)
        for aid in current - members:
            if aid != "main":
                remove_member(group_id, aid)
        bind_group_project(group_id, project_id)
        return True, f"群组已同步: {group_id}", group_id

    group = create_group(
        name=group_name,
        description=group_desc,
        project_id=project_id,
    )
    group_id = group["id"]
    for aid in sorted(members):
        add_member(group_id, aid)
    bind_group_project(group_id, project_id)

    _post_system_message(
        group_id,
        f"🚀 项目群已创建\n项目：{display}\n成员：{', '.join(sorted(members))}",
    )
    return True, f"群组已创建: {group_id}", group_id


def post_project_progress(
    project_id: str,
    text: str,
    *,
    sender: str = "system",
) -> tuple[bool, str]:
    """向绑定项目的群组发送进度通报（无 @ 时不触发 Agent 路由）。"""
    if not skill_config.get("notifications", "use_project_group", default=True):
        return False, "project group notifications disabled"

    group = find_group_by_project(project_id)
    if not group:
        return False, f"no group bound to project {project_id}"

    if group.get("status") == "dissolved":
        restore_group(group["id"])
        group = find_group_by_project(project_id) or group

    ok = _post_system_message(group["id"], text, sender=sender)
    if ok:
        _record_message_event(project_id, sender, text)
        return True, group["id"]
    return False, "failed to post message"


def _record_message_event(project_id: str, sender: str, text: str) -> None:
    """把群通知记进项目事件流（run_event），失败不影响通知本身。"""
    try:
        import sys
        from pathlib import Path
        backend = Path(__file__).resolve().parents[2]
        if str(backend) not in sys.path:
            sys.path.insert(0, str(backend))
        from common.store import Store

        store = Store()
        try:
            store.append_run_event(f"{project_id}:notify", "message",
                                   {"sender": sender, "text": text[:500]})
        finally:
            store.close()
    except Exception:
        pass


def _post_system_message(group_id: str, text: str, sender: str = "system") -> bool:
    try:
        for evt in send_group_message(group_id, sender, text, route_mentions=False):
            publish(group_id, evt)
            if evt.get("event") == "error":
                return False
        return True
    except Exception:
        return False


def _load_task_context(project_id: str, task_id: str, agent_id: str = "") -> tuple[str, str, list[str]]:
    project_name = _resolve_project_display_name(project_id)
    task_name = ""
    deliverables: list[str] = []
    try:
        td = PROJECTS_DIR / project_id / "task_data.json"
        if not td.is_file():
            return project_name, task_name, deliverables
        data = json.loads(td.read_text(encoding="utf-8"))
        project_name = (data.get("project") or {}).get("name", project_name) or project_name
        if task_id:
            for t in data.get("tasks") or []:
                if t.get("id") == task_id:
                    task_name = t.get("name") or task_id
                    agent_id = agent_id or t.get("agent") or ""
                    break
                for st in t.get("subtasks") or []:
                    if st.get("id") == task_id:
                        task_name = st.get("name") or task_id
                        agent_id = agent_id or st.get("agent") or t.get("agent") or ""
                        break
        deliv_dir = PROJECTS_DIR / project_id / "deliverables"
        if task_id and deliv_dir.is_dir():
            for f in sorted(deliv_dir.glob(f"{task_id}*.md")):
                deliverables.append(f.name)
    except Exception:
        pass
    return project_name, task_name, deliverables


def format_progress_message(
    event_type: str,
    project_id: str,
    agent_id: str = "",
    task_id: str = "",
    extra: str = "",
) -> str:
    """统一多行通报（对齐 notify-telegram format_notification）。"""
    import sys

    from hub.paths import BACKEND_DIR

    p = str(BACKEND_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)
    from common.notify_format import format_event_message

    project_name, task_name, deliverables = _load_task_context(project_id, task_id, agent_id)
    subtask_name = ""
    parent_task_name = task_name
    if event_type.startswith("subtask") and task_id:
        subtask_name = task_name
        task_name = parent_task_name

    return format_event_message(
        event_type,
        project_name,
        agent_id=agent_id,
        task_id=task_id,
        task_name=task_name,
        subtask_name=subtask_name,
        deliverables=deliverables if event_type in ("task_complete", "subtask_complete") else None,
        extra=extra,
    )
