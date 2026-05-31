"""
Group Manager - 群组管理 + @mention 路由
"""

import json
import os
import threading
import time
from pathlib import Path
from typing import Generator, Optional

from agent_chat import (
    scan_agents, stream_chat,
    get_agent_backend_config,
)

MYTEAM_DIR = Path(__file__).parent.parent  # myteam/
GROUPS_FILE = MYTEAM_DIR / "data" / "groups.json"

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

def create_group(name: str, description: str = "") -> dict:
    """创建群组"""
    with _lock:
        groups = _load_groups()
        group_id = f"g_{int(time.time())}_{len(groups)}"
        group = {
            "id": group_id,
            "name": name,
            "description": description,
            "members": [],              # agent_id 列表
            "created_at": time.time(),
            "messages": [],             # 消息历史
        }
        groups[group_id] = group
        _save_groups(groups)
    return group


def delete_group(group_id: str) -> bool:
    """删除群组"""
    with _lock:
        groups = _load_groups()
        if group_id in groups:
            del groups[group_id]
            _save_groups(groups)
            return True
    return False


def list_groups() -> list[dict]:
    """列出所有群组"""
    groups = _load_groups()
    result = []
    for gid, g in groups.items():
        # 不返回完整消息历史，只返回摘要
        result.append({
            "id": gid,
            "name": g.get("name", ""),
            "description": g.get("description", ""),
            "members": g.get("members", []),
            "member_count": len(g.get("members", [])),
            "msg_count": len(g.get("messages", [])),
            "created_at": g.get("created_at", 0),
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

    # 路由到被 @ 的 Agent
    for agent_id in mentioned:
        # 提取给这个 Agent 的消息（去掉 @mention 前缀）
        msg_for_agent = _extract_message_for_agent(text, agent_id, members)

        # 获取发送者名称
        sender_name = sender if sender == "user" else f"Agent-{sender}"
        agents_info = {a["id"]: a["name"] for a in scan_agents()}
        sender_display = "用户" if sender == "user" else agents_info.get(sender, sender)

        # 构造上下文
        context = (
            f"[群组: {g['name']}]\n"
            f"[来自: @{sender_display}]\n"
            f"[消息: {msg_for_agent}]\n\n"
            f"请在群组 {g['name']} 中响应此消息。"
            f"完成工作后，请用 @{sender_display} 标记让提需求的人知道。"
        )

        yield {"event": "routing", "data": {
            "to": agent_id,
            "from": sender,
            "message": context,
        }}

        # 调用 Agent
        try:
            for sse_json in stream_chat(agent_id, context):
                evt = json.loads(sse_json)
                if evt["event"] == "thinking":
                    yield {"event": "agent_thinking", "data": {
                        "agent_id": agent_id,
                        "type": evt["data"].get("type", ""),
                        "content": evt["data"].get("content", ""),
                        "name": evt["data"].get("name", ""),
                    }}
                elif evt["event"] == "done":
                    # Agent 完成，保存响应到群消息
                    response_entry = {
                        "id": f"m_{int(time.time()*1000000)}_{agent_id}",
                        "sender": agent_id,
                        "text": f"@{sender} 已完成",
                        "timestamp": time.time(),
                        "mentions": [sender] if sender != "user" else [],
                        "in_reply_to": msg_id,
                    }
                    with _lock:
                        groups = _load_groups()
                        if group_id in groups:
                            groups[group_id].setdefault("messages", []).append(response_entry)
                            _save_groups(groups)

                    yield {"event": "agent_done", "data": {
                        "agent_id": agent_id,
                        "reply_to": sender,
                        "session_id": evt["data"].get("session_id", ""),
                    }}
        except Exception as e:
            yield {"event": "error", "data": {"message": f"Agent '{agent_id}' 响应失败: {e}"}}


def _extract_message_for_agent(text: str, agent_id: str, all_members: list[str]) -> str:
    """提取针对某个 Agent 的消息（去掉 @mention 前缀等）"""
    result = text
    # 去掉本 agent 的 @mention
    result = result.replace(f"@{agent_id}", "").strip()

    # 去掉其他 agent 的 @mention 但保留文字
    for other in all_members:
        if other != agent_id:
            result = result.replace(f"@{other}", f"@{other}").strip()

    return result or text