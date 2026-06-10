"""
Group Manager - 群组管理 + @mention 路由
"""

import json
import threading
import time
from pathlib import Path
from typing import Generator, Optional

from base.agent_chat import (
    get_agent_backend_config,
    scan_agents,
    stream_chat,
)

from hub.paths import GROUPS_FILE
from hub.services.stream_fanout import fanout_stream_event

_lock = threading.Lock()


# ============ 数据持久化 ============

def _load_groups() -> dict:
    try:
        if GROUPS_FILE.exists():
            with open(GROUPS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_groups(data: dict):
    GROUPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(GROUPS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ============ 群组 CRUD ============

def create_group(name: str, description: str = "", project_id: str | None = None) -> dict:
    """创建群组"""
    with _lock:
        groups = _load_groups()
        group_id = f"g_{int(time.time())}_{len(groups)}"
        group = {
            "id": group_id,
            "name": name,
            "description": description,
            "project_id": project_id or "",
            "members": [],              # agent_id 列表
            "created_at": time.time(),
            "messages": [],             # 消息历史
        }
        groups[group_id] = group
        _save_groups(groups)
    return group


def bind_group_project(group_id: str, project_id: str) -> tuple[bool, str]:
    """将群组与项目绑定。"""
    with _lock:
        groups = _load_groups()
        g = groups.get(group_id)
        if not g:
            return False, "群组不存在"
        g["project_id"] = project_id
        _save_groups(groups)
    return True, f"群组已绑定项目 {project_id}"


def find_group_by_project(project_id: str) -> Optional[dict]:
    """按 project_id 查找绑定群组。"""
    if not project_id:
        return None
    groups = _load_groups()
    for g in groups.values():
        if g.get("project_id") == project_id:
            return g
    return None


def delete_group(group_id: str) -> bool:
    """永久删除群组（慎用）。"""
    with _lock:
        groups = _load_groups()
        if group_id in groups:
            del groups[group_id]
            _save_groups(groups)
            return True
    return False


def dissolve_group(group_id: str) -> tuple[bool, str]:
    """解散群组：归档元数据，清空活跃列表，不删 project/tasks。"""
    with _lock:
        groups = _load_groups()
        g = groups.get(group_id)
        if not g:
            return False, "群组不存在"
        if g.get("status") == "dissolved":
            return False, "群组已解散"
        archive = {
            "id": g["id"],
            "name": g.get("name", ""),
            "description": g.get("description", ""),
            "project_id": g.get("project_id", ""),
            "members": g.get("members", []),
            "dissolved_at": time.time(),
            "message_count": len(g.get("messages", [])),
        }
        _append_group_archive(archive)
        g["status"] = "dissolved"
        g["messages"] = []
        g["dissolved_at"] = archive["dissolved_at"]
        _save_groups(groups)
    return True, "群组已解散"


def restore_group(group_id: str) -> tuple[bool, str]:
    """恢复已解散的群组。"""
    with _lock:
        groups = _load_groups()
        g = groups.get(group_id)
        if not g:
            return False, "群组不存在"
        if g.get("status") != "dissolved":
            return False, "群组未解散"
        g["status"] = "active"
        g.pop("dissolved_at", None)
        _save_groups(groups)
    return True, "群组已恢复"


def _append_group_archive(entry: dict):
    from hub.paths import GROUP_ARCHIVES_FILE

    archives = []
    try:
        if GROUP_ARCHIVES_FILE.exists():
            archives = json.loads(GROUP_ARCHIVES_FILE.read_text(encoding="utf-8"))
    except Exception:
        archives = []
    archives.append(entry)
    GROUP_ARCHIVES_FILE.parent.mkdir(parents=True, exist_ok=True)
    GROUP_ARCHIVES_FILE.write_text(
        json.dumps(archives, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def search_groups(query: str, include_dissolved: bool = True) -> list[dict]:
    """检索群组（含已解散）。"""
    q = (query or "").strip().lower()
    groups = _load_groups()
    result = []
    for gid, g in groups.items():
        status = g.get("status", "active")
        if status == "dissolved" and not include_dissolved:
            continue
        name = g.get("name", "").lower()
        desc = g.get("description", "").lower()
        if not q or q in gid.lower() or q in name or q in desc:
            result.append({
                "id": gid,
                "name": g.get("name", ""),
                "description": g.get("description", ""),
                "project_id": g.get("project_id", ""),
                "members": g.get("members", []),
                "status": status,
                "member_count": len(g.get("members", [])),
                "msg_count": len(g.get("messages", [])),
                "last_message_at": _last_message_ts(g),
                "created_at": g.get("created_at", 0),
                "dissolved_at": g.get("dissolved_at"),
            })
    return sorted(result, key=lambda x: x.get("last_message_at", x.get("created_at", 0)), reverse=True)


def _last_message_ts(g: dict) -> float:
    msgs = g.get("messages") or []
    if not msgs:
        return g.get("created_at", 0)
    return max(m.get("timestamp", 0) for m in msgs)


def clear_group_messages(group_id: str) -> tuple[bool, str]:
    """清空群组消息历史（界面记录）"""
    with _lock:
        groups = _load_groups()
        if group_id not in groups:
            return False, "群组不存在"
        groups[group_id]["messages"] = []
        _save_groups(groups)
    return True, "群组消息已清空"


def update_group_meta(
    group_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
) -> tuple[bool, str]:
    """更新群组名称/描述。"""
    with _lock:
        groups = _load_groups()
        g = groups.get(group_id)
        if not g:
            return False, "群组不存在"
        if name is not None:
            g["name"] = name
        if description is not None:
            g["description"] = description
        _save_groups(groups)
    return True, "已更新"


def list_groups(include_dissolved: bool = False) -> list[dict]:
    """列出群组；默认不含已解散。"""
    groups = _load_groups()
    result = []
    for gid, g in groups.items():
        status = g.get("status", "active")
        if status == "dissolved" and not include_dissolved:
            continue
        result.append({
            "id": gid,
            "name": g.get("name", ""),
            "description": g.get("description", ""),
            "project_id": g.get("project_id", ""),
            "members": g.get("members", []),
            "status": status,
            "member_count": len(g.get("members", [])),
            "msg_count": len(g.get("messages", [])),
            "last_message_at": _last_message_ts(g),  # 与 search_groups() 字段对齐；重启后按最近活跃排序的依据
            "created_at": g.get("created_at", 0),
            "dissolved_at": g.get("dissolved_at"),
        })
    return sorted(result, key=lambda x: x.get("created_at", 0))


def get_group(group_id: str) -> Optional[dict]:
    """获取群组详情（含最近消息）"""
    groups = _load_groups()
    g = groups.get(group_id)
    if g:
        return {
            "id": g["id"],
            "name": g["name"],
            "description": g.get("description", ""),
            "project_id": g.get("project_id", ""),
            "members": g.get("members", []),
            "created_at": g.get("created_at", 0),
            "messages": g.get("messages", [])[-50:],  # 最近 50 条
        }
    return None


# ============ 成员管理 ============

def add_member(group_id: str, agent_id: str) -> tuple[bool, str]:
    """添加 Agent 到群组"""
    with _lock:
        groups = _load_groups()
        g = groups.get(group_id)
        if not g:
            return False, "群组不存在"
        # 检查 agent 是否存在
        agents = scan_agents()
        if not any(a["id"] == agent_id for a in agents):
            return False, f"Agent '{agent_id}' 不存在"
        if agent_id in g.get("members", []):
            return False, f"Agent '{agent_id}' 已在群组中"
        g.setdefault("members", []).append(agent_id)
        _save_groups(groups)
    return True, f"已添加 {agent_id}"


def remove_member(group_id: str, agent_id: str) -> tuple[bool, str]:
    """从群组移除 Agent"""
    with _lock:
        groups = _load_groups()
        g = groups.get(group_id)
        if not g:
            return False, "群组不存在"
        members = g.get("members", [])
        if agent_id not in members:
            return False, f"Agent '{agent_id}' 不在群组中"
        g["members"] = [m for m in members if m != agent_id]
        _save_groups(groups)
    return True, f"已移除 {agent_id}"


# ============ @mention 路由 ============

def resolve_mentions(text: str, group_members: list[str]) -> list[str]:
    """从文本中解析 @mention 的 agent_id 列表"""
    mentioned = []
    for agent_id in group_members:
        if f"@{agent_id}" in text:
            mentioned.append(agent_id)
    return mentioned


def send_group_message(
    group_id: str,
    sender: str,    # "user" 或 agent_id
    text: str,
    cancel_event=None,
    route_mentions: bool | None = None,
    route_only: bool = False,
) -> Generator[dict, None, None]:
    """
    在群组中发送消息，自动处理 @mention 路由

    Args:
        group_id: 群组 ID
        sender: 发送者 ("user" 或 agent_id)
        text: 消息文本

    Yields:
        dict: 处理结果事件
    """
    groups = _load_groups()
    g = groups.get(group_id)
    if not g:
        yield {"event": "error", "data": {"message": "群组不存在"}}
        return

    members = g.get("members", [])

    # 保存消息到历史
    msg_id = f"m_{int(time.time()*1000000)}"
    msg_entry = {
        "id": msg_id,
        "sender": sender,
        "text": text,
        "timestamp": time.time(),
        "mentions": [],
    }

    # 解析 @mention
    mentioned = resolve_mentions(text, members)

    if not mentioned:
        # 纯聊天，保存即可
        yield {"event": "group_message", "data": {
            "msg_id": msg_id, "sender": sender, "text": text,
            "mentions": [],
        }}
        with _lock:
            groups = _load_groups()
            if group_id in groups:
                groups[group_id].setdefault("messages", []).append(msg_entry)
                _save_groups(groups)
        return

    msg_entry["mentions"] = mentioned
    yield {"event": "group_message", "data": {
        "msg_id": msg_id, "sender": sender, "text": text,
        "mentions": mentioned,
    }}

    # 保存消息
    with _lock:
        groups = _load_groups()
        if group_id in groups:
            groups[group_id].setdefault("messages", []).append(msg_entry)
            _save_groups(groups)

    # 仅用户 @mention 或显式 route_mentions 时触发 Agent 调度
    if route_mentions is None:
        route_mentions = sender == "user"
    if not route_mentions:
        return

    for agent_id in mentioned:
        if cancel_event and cancel_event.is_set():
            yield {"event": "error", "data": {"message": "已取消"}}
            return

        # 提取给这个 Agent 的消息（去掉 @mention 前缀）
        msg_for_agent = _extract_message_for_agent(text, agent_id, members)

        # 获取发送者名称
        sender_name = sender if sender == "user" else f"Agent-{sender}"
        agents_info = {a["id"]: a["name"] for a in scan_agents()}
        sender_display = "用户" if sender == "user" else agents_info.get(sender, sender)

        # 构造上下文（不要求 Agent 在群内 @ 回，避免 Agent 互 @ 死循环）
        context = (
            f"[群组: {g['name']}]\n"
            f"[来自: @{sender_display}]\n"
            f"[消息: {msg_for_agent}]\n\n"
            f"这是群组任务通知。请执行上述工作。"
            f"完成后用简短文字总结即可，不要在回复中 @ 其他 Agent。"
        )

        yield {"event": "routing", "data": {
            "to": agent_id,
            "from": sender,
            "message": context,
        }}

        if route_only:
            def _bg():
                for _ in _stream_agent_in_group(
                    group_id, agent_id, context, msg_id, cancel_event, as_generator=True,
                ):
                    pass

            threading.Thread(target=_bg, daemon=True).start()
            continue

        yield from _stream_agent_in_group(
            group_id, agent_id, context, msg_id, cancel_event, as_generator=True,
        )


def _stream_agent_in_group(
    group_id: str,
    agent_id: str,
    context: str,
    msg_id: str,
    cancel_event=None,
    *,
    as_generator: bool = False,
):
    """在群组上下文中运行 Agent 流；as_generator=True 时 yield 事件。"""
    try:
        for sse_json in stream_chat(agent_id, context, cancel_event=cancel_event):
            if cancel_event and cancel_event.is_set():
                err = {"event": "error", "data": {"message": "已取消"}}
                if as_generator:
                    yield err
                return
            fanout_stream_event(agent_id, sse_json, group_id=group_id)
            evt = json.loads(sse_json)
            thinking = _sse_to_thinking(evt)
            if thinking:
                out = {"event": "agent_thinking", "data": {
                    "agent_id": agent_id,
                    **thinking,
                }}
                if as_generator:
                    yield out
            elif evt.get("event") == "done":
                summary = evt.get("data", {}).get("summary", "") or "已完成"
                preview = summary[:200] if summary else "已完成"
                response_entry = {
                    "id": f"m_{int(time.time()*1000000)}_{agent_id}",
                    "sender": agent_id,
                    "text": preview,
                    "timestamp": time.time(),
                    "mentions": [],
                    "in_reply_to": msg_id,
                }
                with _lock:
                    groups = _load_groups()
                    if group_id in groups:
                        groups[group_id].setdefault("messages", []).append(response_entry)
                        _save_groups(groups)

                done_evt = {"event": "agent_done", "data": {
                    "agent_id": agent_id,
                    "reply_to": "system",
                    "session_id": evt.get("data", {}).get("session_id", ""),
                }}
                if as_generator:
                    yield done_evt
    except Exception as e:
        err = {"event": "error", "data": {"message": f"Agent '{agent_id}' 响应失败: {e}"}}
        if as_generator:
            yield err


def _sse_to_thinking(evt: dict) -> Optional[dict]:
    """将 stream_chat 的 SSE 事件转为 thinking 展示格式（群组用）"""
    if evt.get("event") == "thinking":
        return evt.get("data")
    return None


def _extract_message_for_agent(text: str, agent_id: str, all_members: list[str]) -> str:
    """提取针对某个 Agent 的消息（去掉 @mention 前缀等）"""
    result = text
    result = result.replace(f"@{agent_id}", "").strip()
    for other in all_members:
        if other != agent_id:
            result = result.replace(f"@{other}", f"@{other}").strip()
    return result or text