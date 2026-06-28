"""
from common.coordinator import get_coordinator_id
Group Manager - 群组管理 + @mention 路由
"""

import json
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Generator, Optional

from base.agent_chat import (
    get_agent_backend_config,
    scan_agents,
    stream_chat,
)

from hub.paths import GROUPS_FILE, TASKS_DIR, to_relative_path
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
                "last_message": _last_message_preview(g),
                "created_at": g.get("created_at", 0),
                "dissolved_at": g.get("dissolved_at"),
            })
    return sorted(result, key=lambda x: x.get("last_message_at", x.get("created_at", 0)), reverse=True)


def _last_message_ts(g: dict) -> float:
    msgs = g.get("messages") or []
    if not msgs:
        return g.get("created_at", 0)
    return max(m.get("timestamp", 0) for m in msgs)


def _last_message_preview(g: dict, limit: int = 80) -> str:
    msgs = g.get("messages") or []
    if not msgs:
        return ""
    last = max(msgs, key=lambda m: m.get("timestamp", 0))
    text = (last.get("text") or "").replace("\n", " ").strip()
    return text[:limit]


def clear_group_messages(group_id: str) -> tuple[bool, str]:
    """清空群组消息历史，并清除该群 scoped 的 Agent 会话记忆（不动 DM / 团队 KB）。"""
    member_ids: list[str] = []
    with _lock:
        groups = _load_groups()
        if group_id not in groups:
            return False, "群组不存在"
        g = groups[group_id]
        member_ids = list(g.get("members") or [])
        groups[group_id]["messages"] = []
        _save_groups(groups)
    try:
        from common.agent_memory import clear_group_agent_memory

        clear_group_agent_memory(group_id, member_ids)
    except Exception as e:
        return True, f"群组消息已清空（会话记忆清理部分失败: {e}）"
    try:
        from hub.services.group_broadcast import publish as publish_group

        publish_group(group_id, {"event": "group_cleared", "data": {}})
    except Exception:
        pass
    return True, "群组消息与群会话记忆已清空"


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


def update_group_roundtable_settings(
    group_id: str,
    *,
    facilitator: str | None = None,
    max_rounds: int | None = None,
) -> tuple[bool, str]:
    """更新群组圆桌设置：主持人、最大讨论轮数。"""
    with _lock:
        groups = _load_groups()
        g = groups.get(group_id)
        if not g:
            return False, "群组不存在"
        members = g.get("members") or []
        if facilitator is not None:
            fac = facilitator.strip()
            if fac and fac not in members:
                return False, f"主持人 '{fac}' 不是群成员"
            if fac:
                g["roundtable_facilitator"] = fac
            else:
                g.pop("roundtable_facilitator", None)
        if max_rounds is not None:
            cap = max_roundtable_rounds_cap()
            rounds = max(1, min(int(max_rounds), cap))
            g["roundtable_max_rounds"] = rounds
        _save_groups(groups)
    return True, "圆桌设置已更新"


def _group_roundtable_fields(g: dict) -> dict:
    default_rounds = _default_roundtable_max_rounds()
    return {
        "roundtable_facilitator": g.get("roundtable_facilitator") or "",
        "roundtable_max_rounds": int(
            g.get("roundtable_max_rounds") or default_rounds
        ),
        "roundtable_uses_global_max_rounds": "roundtable_max_rounds" not in g,
    }


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
            "last_message": _last_message_preview(g),
            "created_at": g.get("created_at", 0),
            "dissolved_at": g.get("dissolved_at"),
            **_group_roundtable_fields(g),
        })
    return sorted(result, key=lambda x: x.get("last_message_at", x.get("created_at", 0)), reverse=True)


def _agent_display_names_for_members(members: list[str]) -> dict[str, str]:
    """群成员 id → 展示名（注册表中文名优先）。"""
    from hub.services.agent_registry import get_agents_registry

    scanned = {a["id"]: a.get("name") or a["id"] for a in scan_agents()}
    reg_agents = get_agents_registry().get("agents") or {}
    out: dict[str, str] = {}
    for aid in members:
        if aid == "user":
            out[aid] = "你"
            continue
        if aid == "system":
            out[aid] = "系统"
            continue
        reg_name = (reg_agents.get(aid) or {}).get("name")
        out[aid] = (reg_name or scanned.get(aid) or aid).strip()
    return out


def get_group(group_id: str) -> Optional[dict]:
    """获取群组详情（含最近消息）"""
    groups = _load_groups()
    g = groups.get(group_id)
    if g:
        members = g.get("members", [])
        from common.group_message_store import resolve_group_messages_for_api

        messages = resolve_group_messages_for_api(
            group_id,
            g.get("messages", []),
            limit=50,
        )
        return {
            "id": g["id"],
            "name": g["name"],
            "description": g.get("description", ""),
            "project_id": g.get("project_id", ""),
            "members": members,
            "agent_names": _agent_display_names_for_members(members),
            "created_at": g.get("created_at", 0),
            "messages": messages,
            **_group_roundtable_fields(g),
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
        if g.get("roundtable_facilitator") == agent_id:
            g.pop("roundtable_facilitator", None)
        _save_groups(groups)
    return True, f"已移除 {agent_id}"


def reorder_group_members(group_id: str, member_ids: list[str]) -> tuple[bool, str]:
    """调整群成员顺序（圆桌立论/对齐轮发言顺序依此列表，不含主持人）。"""
    with _lock:
        groups = _load_groups()
        g = groups.get(group_id)
        if not g:
            return False, "群组不存在"
        current = list(g.get("members") or [])
        if not current:
            return False, "群组暂无成员"
        ordered = [str(m).strip() for m in member_ids if str(m).strip()]
        if len(ordered) != len(current):
            return False, "成员数量与当前群组不一致"
        if set(ordered) != set(current):
            return False, "成员列表与当前群组不一致"
        g["members"] = ordered
        _save_groups(groups)
    return True, "成员顺序已更新"

ROUNDTABLE_DIR = TASKS_DIR / "group_roundtables"

DEFAULT_ROUNDTABLE_MAX_ROUNDS = 3
MIN_ALIGNMENT_CYCLES_BEFORE_EARLY_CONSENSUS = 1  # 至少一轮全员对齐后才可发起共识草案
MAX_CONSENSUS_CONFIRM_ATTEMPTS = 6  # 共识确认轮上限，防止死循环


def _default_roundtable_max_rounds() -> int:
    try:
        from common.skill_settings import group_discussion_default_max_rounds

        return group_discussion_default_max_rounds(DEFAULT_ROUNDTABLE_MAX_ROUNDS)
    except Exception:
        return DEFAULT_ROUNDTABLE_MAX_ROUNDS


def max_roundtable_rounds_cap() -> int:
    try:
        from common.skill_settings import roundtable_max_rounds_cap

        return roundtable_max_rounds_cap(50)
    except Exception:
        return 50


def _roundtable_quorum_ratio() -> float:
    try:
        from common.skill_settings import roundtable_quorum_ratio

        return roundtable_quorum_ratio(2 / 3)
    except Exception:
        return 2 / 3


# 向后兼容测试引用
MAX_ROUNDTABLE_ROUNDS_CAP = 50
ROUNDTABLE_QUORUM_RATIO = 2 / 3


def _strip_command_prefix(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^@(?:all|everyone)\s+", "", t, flags=re.IGNORECASE).strip()
    return t


def is_roundtable_terminate_command(text: str) -> bool:
    """用户终止讨论命令（无需 @mention）。"""
    try:
        from common.skill_settings import roundtable_terminate_commands

        commands = roundtable_terminate_commands()
    except Exception:
        commands = ["/终止讨论", "/终止圆桌", "/stop roundtable"]
    cmd_text = _strip_command_prefix(text).lower()
    for raw in commands:
        cl = raw.strip().lower()
        if not cl:
            continue
        if cmd_text == cl or cmd_text.startswith(cl + " "):
            return True
    return False

_CONSENSUS_YES_RE = re.compile(
    r"CONSENSUS:\s*YES|已达成共识|可以照此执行", re.IGNORECASE,
)
_CONSENSUS_NEED_RE = re.compile(
    r"CONSENSUS:\s*NEED_MORE|仍有分歧|尚不一致|需继续讨论", re.IGNORECASE,
)
_CONSENSUS_PROPOSED_RE = re.compile(
    r"CONSENSUS:\s*PROPOSED|共识草案已发布|提交共识确认", re.IGNORECASE,
)
_BEST_PRACTICE_PROPOSED_RE = re.compile(
    r"BEST_PRACTICE:\s*PROPOSED|最佳实践草案已发布|提交最佳实践确认", re.IGNORECASE,
)
_BEST_PRACTICE_NEED_RE = re.compile(
    r"BEST_PRACTICE:\s*NEED_MORE|最佳实践尚未成熟", re.IGNORECASE,
)
_CONSENSUS_VOTE_AGREE_RE = re.compile(
    r"CONSENSUS_VOTE:\s*(?:AGREE|同意)", re.IGNORECASE,
)
_CONSENSUS_VOTE_OBJECT_RE = re.compile(
    r"CONSENSUS_VOTE:\s*(?:OBJECT|反对)", re.IGNORECASE,
)
_CONSENSUS_VOTE_ABSTAIN_RE = re.compile(
    r"CONSENSUS_VOTE:\s*(?:ABSTAIN|弃权)", re.IGNORECASE,
)
_INVALID_ROUNDTABLE_REPLY_RE = re.compile(
    r"\.trigger|\.response|phase\s*=\s*(?:evaluate|execute)|读取.*trigger|检查.*trigger",
    re.IGNORECASE,
)

DISCUSS_PROMPT_HINT = (
    "本轮为群组讨论/圆桌（讨论模式）：全程以**用户话题**为锚点，从本角色专业视角"
    "参与多专业交叉验证——指出依据、风险、待验证项，避免空泛附和；"
    "需要时可使用 WebSearch/WebFetch/Read/Grep 调研。"
)


def _roundtable_topic_block(agenda: str) -> str:
    """各阶段共用的用户话题锚点（讨论与终稿均须相对此话题）。"""
    topic = (agenda or "").strip() or "（未指定）"
    return (
        f"## 用户话题（全程锚点，不得答偏）\n{topic}\n\n"
        "圆桌目标：各角色独立贡献 → **交叉验证理解** → 对齐交锋 → "
        "形成**针对本话题的最佳实践**（可执行、可验证、保留真实分歧）。"
        "若发现讨论重心偏离上述话题，须在本轮指出并拉回。"
    )

ROLE_HINTS: dict[str, str] = {
    "product": "从产品需求、验收标准、用户价值角度发言。",
    "arch": "从系统架构、技术可行性、模块边界角度发言。",
    "research": "从调研、竞品、数据与事实依据角度发言。",
    get_coordinator_id(): "从项目规划、优先级编排、跨角色协调角度发言。",
    "docs": "从文档结构、交付物规范角度发言。",
    "geo": "从 GEO/SEO 持续优化角度发言。",
    "frontend": "从前端架构、Hub/UI 实现角度发言。",
    "content": "从内容策略、运营节奏角度发言。",
    "developer": "从后端实现、代码结构、可靠性工程与可测试性角度发言。",
    "ops": "从部署运维、可观测性、故障恢复与上线风险角度发言。",
    "qa": "从测试策略、验收标准、边界场景与质量门禁角度发言；"
    "重点指出「按当前共识执行仍可能测不到、仍可能线上出问题」的场景。",
}


_ROUNDTABLE_CROSS_CHECK = (
    "- 须做**交叉验证**：至少 1 条本专业依据、风险或待验证项；禁止无具体内容的「同意」「没问题」\n"
    "- 所有结论须能回答**用户话题**；勿擅自换成无关议题（如用户问现状分析却只排优先级）"
)


def resolve_mentions(text: str, group_members: list[str]) -> list[str]:
    """从文本中解析 @mention 的 agent_id 列表（含 @all / @everyone）。"""
    if re.search(r"@(?:all|everyone)\b", text, re.IGNORECASE):
        return list(group_members)
    mentioned = []
    for agent_id in group_members:
        if f"@{agent_id}" in text:
            mentioned.append(agent_id)
    return mentioned


def detect_group_mode(text: str, mentioned: list[str]) -> str:
    """@all / @everyone → 圆桌；@一个或多个具体 Agent → 群聊回复（同私聊逻辑）。"""
    if not mentioned:
        return "notify"
    if re.search(r"@(?:all|everyone)\b", text, re.IGNORECASE):
        return "roundtable"
    return "notify"


def _default_roundtable_facilitator(members: list[str]) -> str:
    """未配置主持人时：群成员列表第一位（加入顺序）。"""
    return members[0] if members else ""


def format_group_context(
    g: dict,
    *,
    exclude_msg_id: str | None = None,
    limit: int = 40,
) -> str:
    """格式化群消息历史，供 @回复与圆桌 prompt 共用。"""
    messages = g.get("messages") or []
    lines: list[str] = []
    for m in messages[-limit:]:
        if exclude_msg_id and m.get("id") == exclude_msg_id:
            continue
        sender = m.get("sender") or "unknown"
        text = (m.get("text") or "").strip()
        if not text:
            continue
        if m.get("roundtable"):
            phase = m.get("roundtable_phase") or "roundtable"
            lines.append(f"[圆桌·{phase}] @{sender}: {text}")
        elif sender == "system":
            lines.append(f"[系统]: {text}")
        else:
            lines.append(f"@{sender}: {text}")
    return "\n".join(lines) if lines else "（暂无群聊历史）"


_CONTINUE_AGENDA_RE = re.compile(
    r"^(?:继续|接着|往下(?:讨论)?|继续讨论|接着讨论|go\s*on|continue)\.?$",
    re.IGNORECASE,
)
_TRANSCRIPT_AGENDA_RE = re.compile(r"^议题:\s*(.+)$", re.MULTILINE)


def latest_roundtable_agenda(group_id: str) -> str:
    """读取该群最近一次圆桌 transcript 的有效议题（跳过「继续」类占位）。"""
    group_dir = ROUNDTABLE_DIR / group_id
    if not group_dir.is_dir():
        return ""
    paths = sorted(
        group_dir.glob("m_*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in paths:
        try:
            head = path.read_text(encoding="utf-8")[:4096]
        except OSError:
            continue
        match = _TRANSCRIPT_AGENDA_RE.search(head)
        if not match:
            continue
        agenda = match.group(1).strip()
        if agenda and not _CONTINUE_AGENDA_RE.match(agenda):
            return agenda
    return ""


def extract_agenda(
    text: str,
    members: list[str],
    *,
    prior_agenda: str = "",
) -> str:
    """去掉 @mention 后得到讨论议题；「继续」等续接词继承 prior_agenda。"""
    result = text
    result = re.sub(r"@(?:all|everyone)\b", "", result, flags=re.IGNORECASE)
    for agent_id in members:
        result = result.replace(f"@{agent_id}", "")
    stripped = result.strip() or text.strip()
    if prior_agenda and _CONTINUE_AGENDA_RE.match(stripped):
        return prior_agenda
    return stripped


def roundtable_speaker_order(participants: list[str], members: list[str] | None = None) -> list[str]:
    """立论/对齐轮发言顺序（不含主持人），按群成员列表顺序排列。"""
    if not members:
        return list(participants)
    order = {m: i for i, m in enumerate(members)}
    return sorted(participants, key=lambda aid: order.get(aid, len(members)))


def resolve_roundtable_settings(
    g: dict,
    mentioned: list[str] | None = None,
    *,
    rounds_override: int | None = None,
) -> tuple[str, int, list[str]]:
    """解析主持人、最大轮数、参与讨论成员（全员除主持人，按成员列表顺序）。"""
    del mentioned  # 圆桌参与者固定为群全员，与 @ 列表无关
    members = g.get("members") or []
    raw_rounds = (
        rounds_override
        if rounds_override is not None
        else g.get("roundtable_max_rounds", _default_roundtable_max_rounds())
    )
    try:
        max_rounds = max(1, min(int(raw_rounds), max_roundtable_rounds_cap()))
    except (TypeError, ValueError):
        max_rounds = _default_roundtable_max_rounds()

    facilitator = str(g.get("roundtable_facilitator") or "").strip()
    if facilitator and facilitator not in members:
        facilitator = ""
    if not facilitator:
        facilitator = _default_roundtable_facilitator(members)

    participants = roundtable_speaker_order(
        [m for m in members if m != facilitator],
        members,
    )
    return facilitator, max_rounds, participants


def roundtable_participation_rate(spoke: dict[str, bool]) -> float:
    """已成功发言的参与者比例。"""
    if not spoke:
        return 0.0
    return sum(1 for ok in spoke.values() if ok) / len(spoke)


def roundtable_quorum_met(spoke: dict[str, bool]) -> bool:
    """严格条件：至少 quorum_ratio 参与者完成至少一轮有效发言。"""
    return roundtable_participation_rate(spoke) >= _roundtable_quorum_ratio()


def should_extend_roundtable_cycles(
    *,
    consensus_status: str,
    cycle: int,
    configured_max: int,
    effective_max: int,
    spoke: dict[str, bool],
) -> bool:
    """突破配置轮数上限：仅 NEED_MORE + 已达配置上限 + quorum 参与 + 未触顶 + 允许扩展。"""
    if consensus_status != "need_more":
        return False
    if cycle < configured_max:
        return False
    cap = max_roundtable_rounds_cap()
    if effective_max >= cap:
        return False
    try:
        from common.skill_settings import group_discussion_allow_round_extension

        if not group_discussion_allow_round_extension():
            return False
    except Exception:
        pass
    return roundtable_quorum_met(spoke)


def accept_early_consensus(
    consensus_status: str,
    spoke: dict[str, bool],
    *,
    alignment_cycles_completed: int = 0,
) -> bool:
    """已废弃：圆桌不再因主持 CONSENSUS: YES 提前结束，改由共识确认轮投票。"""
    del consensus_status, spoke, alignment_cycles_completed
    return False


def consensus_majority_threshold(participant_count: int) -> int:
    """共识确认通过所需的「同意」票数下限（严格多数：ceil(n/2)）。"""
    if participant_count <= 0:
        return 0
    return math.ceil(participant_count / 2)


def consensus_agree_threshold(participant_count: int) -> int:
    """兼容别名：共识确认所需最少同意票（= 严格多数阈值）。"""
    return consensus_majority_threshold(participant_count)


def consensus_vote_stats(
    votes: dict[str, str],
    speakers: list[str],
) -> dict[str, int]:
    agree = sum(1 for s in speakers if votes.get(s) == "agree")
    object_ = sum(1 for s in speakers if votes.get(s) == "object")
    abstain = sum(1 for s in speakers if votes.get(s) == "abstain")
    unknown = len(speakers) - agree - object_ - abstain
    return {
        "agree": agree,
        "object": object_,
        "abstain": abstain,
        "unknown": unknown,
        "total": len(speakers),
    }


def parse_best_practice_status(text: str) -> str:
    """主持最佳实践草案：proposed | need_more | unknown。"""
    if _BEST_PRACTICE_PROPOSED_RE.search(text):
        return "proposed"
    if _BEST_PRACTICE_NEED_RE.search(text):
        return "need_more"
    return "unknown"


def parse_facilitator_draft_status(text: str) -> str:
    """主持最佳实践/共识草案：proposed | need_more | unknown。"""
    bp = parse_best_practice_status(text)
    if bp != "unknown":
        return bp
    if _CONSENSUS_PROPOSED_RE.search(text):
        return "proposed"
    if _CONSENSUS_NEED_RE.search(text) or _BEST_PRACTICE_NEED_RE.search(text):
        return "need_more"
    if _CONSENSUS_YES_RE.search(text):
        return "proposed"
    if any(
        marker in text
        for marker in (
            "## 推荐做法",
            "## 本题最佳实践",
            "## 共识草案",
            "## 对用户话题的共识回答",
        )
    ):
        return "proposed"
    return "unknown"


def parse_consensus_vote(text: str) -> str:
    """共识确认表态：agree | object | abstain | unknown。"""
    from common.roundtable_runtime import sanitize_roundtable_public_text

    text = sanitize_roundtable_public_text(text or "")
    if _CONSENSUS_VOTE_OBJECT_RE.search(text):
        return "object"
    if _CONSENSUS_VOTE_AGREE_RE.search(text):
        return "agree"
    if _CONSENSUS_VOTE_ABSTAIN_RE.search(text):
        return "abstain"
    if re.search(r"^反对$|我反对|不能同意", text.strip(), re.MULTILINE):
        return "object"
    if re.search(r"^同意$|我同意|无异议", text.strip(), re.MULTILINE):
        return "agree"
    return "unknown"


def consensus_confirm_passed(
    votes: dict[str, str],
    speakers: list[str],
) -> bool:
    """少数服从多数：同意票 > 反对票，且同意票 ≥ ceil(n/2)。"""
    if not speakers:
        return False
    stats = consensus_vote_stats(votes, speakers)
    threshold = consensus_majority_threshold(len(speakers))
    return stats["agree"] > stats["object"] and stats["agree"] >= threshold


def format_consensus_objections(
    votes: dict[str, str],
    replies: dict[str, str],
    agents_info: dict[str, str],
) -> str:
    """汇总共识确认轮中的反对意见，供下一轮交锋。"""
    lines: list[str] = [
        "## [系统] 共识确认未通过（对用户话题的共识尚未被多数接受：同意须 > 反对 且 ≥ 半数）\n",
    ]
    for agent_id in sorted(replies):
        vote = votes.get(agent_id, "unknown")
        name = agents_info.get(agent_id, agent_id)
        if vote == "object":
            lines.append(f"### @{agent_id}（{name}）· 反对\n")
            lines.append(replies[agent_id].strip())
            lines.append("")
        elif vote in ("unknown", "abstain"):
            lines.append(
                f"### @{agent_id}（{name}）· {vote}\n"
                f"{replies[agent_id].strip()[:500]}\n",
            )
    return "\n".join(lines).strip()


def parse_consensus_status(text: str) -> str:
    """返回 yes | need_more | unknown。"""
    if _CONSENSUS_YES_RE.search(text):
        return "yes"
    if _CONSENSUS_NEED_RE.search(text):
        return "need_more"
    if "未达成共识" in text or "分歧" in text:
        return "need_more"
    return "unknown"


def is_invalid_roundtable_reply(text: str) -> bool:
    """检测误走 worker-template / trigger 任务流的回复。"""
    stripped = (text or "").strip()
    if not stripped:
        return True
    if _INVALID_ROUNDTABLE_REPLY_RE.search(stripped) and len(stripped) < 400:
        return True
    if stripped in ("已完成", "完成", "done"):
        return True
    return False


def _roundtable_role_hint(agent_id: str, *, phase: str) -> str:
    hint = ROLE_HINTS.get(agent_id, "从本角色专业角度对用户话题发表看法。")
    if phase == "alignment":
        return (
            hint
            + " 请基于主持人汇总做**理解校验**：先复述对方具体观点，再表态"
            "（同意/修正/补充/仍反对）并给出理由；须引用汇总中的具体条目；"
            "保持简洁，不要重复立论全文。"
        )
    if phase == "opening":
        return (
            hint
            + " 请从本角色专业视角独立建观点，直接贡献于**用户话题**："
            "先讲清楚「对本话题的判断、依据、建议怎么做」。"
        )
    if phase == "thinking":
        return (
            hint
            + " 请独立分析**用户话题**，形成初步专业判断，无需预判他人观点或终局结论。"
        )
    if phase == "consensus_confirm":
        return (
            hint
            + " 请从本专业判断：当前**最佳实践**是否**充分、正确地回答了用户话题**，"
            "是否还有本专业不能接受或未覆盖的点。"
        )
    return hint


def _roundtable_transcript_path(group_id: str, msg_id: str) -> Path:
    return ROUNDTABLE_DIR / group_id / f"{msg_id}.md"


def _roundtable_prior(
    transcript_lines: list[str],
    *,
    max_chars: int = 12000,
    mode: str = "digest",
) -> str:
    from common.roundtable_context import (
        compress_transcript_prior,
        extract_conflict_digest_from_transcript,
    )

    raw = "".join(transcript_lines[4:]).strip() if len(transcript_lines) > 4 else ""
    if mode == "conflicts":
        return extract_conflict_digest_from_transcript(raw, max_chars=min(max_chars, 3200))
    return compress_transcript_prior(raw, max_chars=max_chars)


def _build_roundtable_thinking_prompt(
    group_name: str,
    agent_id: str,
    agent_name: str,
    role_hint: str,
    agenda: str,
    group_context: str,
) -> str:
    return (
        f"[群组圆桌 · 独立思考 · {group_name}]\n"
        f"你是 **{agent_name}**（@{agent_id}）。{role_hint}\n\n"
        f"{DISCUSS_PROMPT_HINT}\n\n"
        f"{_roundtable_topic_block(agenda)}\n\n"
        f"## 群聊上下文\n{group_context}\n\n"
        "---\n\n"
        "请**独立**思考用户话题（无需等待他人，也无需预判分歧或终局）。要求：\n"
        "- 用中文，结构化（## 小标题 + 列表）\n"
        "- 缺少事实时可先用 WebSearch/WebFetch/Read/Grep 调研\n"
        "- 必须包含：`## 我对用户问题的理解`、`## 本专业关键判断`、`## 依据`、"
        "`## 待其他角色验证的点`\n"
        f"{_ROUNDTABLE_CROSS_CHECK}\n"
        "- **不要**写「待用户拍板」「保守方案」「与其他角色可能的分歧」等终局内容\n"
        "- 不要 @ 其他 Agent，不要 JSON\n"
        "- 仅输出你的独立思考正文（后续将按顺序在群内立论发言）"
    )


def _build_roundtable_opening_prompt(
    group_name: str,
    agent_id: str,
    agent_name: str,
    role_hint: str,
    agenda: str,
    transcript: str,
    group_context: str,
    prior_thinking: str,
) -> str:
    from common.roundtable_context import digest_for_prompt

    prior = transcript.strip() or "（暂无，你是第一位发言者）"
    thinking_block = digest_for_prompt(
        prior_thinking.strip() if prior_thinking.strip() else "（无独立思考记录）",
        max_chars=1200,
    )
    return (
        f"[群组圆桌 · 立论轮 · {group_name}]\n"
        f"你是 **{agent_name}**（@{agent_id}）。{role_hint}\n\n"
        f"{DISCUSS_PROMPT_HINT}\n\n"
        f"{_roundtable_topic_block(agenda)}\n\n"
        f"## 群聊上下文\n{group_context}\n\n"
        f"## 你刚才的独立思考（要点摘要）\n{thinking_block}\n\n"
        f"## 此前发言要点（摘要，非全文）\n{prior}\n\n"
        "---\n\n"
        "请基于独立思考与群内前文要点，发表**正式立论**（直接贡献于用户话题）。要求：\n"
        "- 用中文，结构化（## 小标题 + 列表）\n"
        "- 必须包含：`## 对用户话题的核心观点`、`## 依据`、"
        "`## 本题最佳实践要点（本角色贡献）`\n"
        "- 须含 `## 本专业风险或待验证项`（至少 1 条；即使总体认同也须写出）\n"
        "- 若前文已有其他角色发言且你持不同意见，**可选**增加 `## 不同看法`（"
        "写明对方观点、你的理由、可接受的修正）；若无不同意见则**省略**该节\n"
        f"{_ROUNDTABLE_CROSS_CHECK}\n"
        "- **不要**写「待用户拍板」「保守方案」或预测其他角色尚未发表的观点\n"
        "- 可引用调研结论；从本角色专业视角发言\n"
        "- **不要复述**前文摘要已有内容；不要 @ 其他 Agent，不要 JSON\n"
        "- 仅输出你本轮的发言内容"
    )


def _build_roundtable_alignment_prompt(
    group_name: str,
    agent_id: str,
    agent_name: str,
    role_hint: str,
    agenda: str,
    facilitator_summary: str,
    conflict_digest: str,
    group_context: str,
    *,
    round_num: int,
) -> str:
    from common.roundtable_context import digest_for_prompt

    fac_block = digest_for_prompt(facilitator_summary, max_chars=2200)
    conflicts = conflict_digest.strip() or "（暂无）"
    return (
        f"[群组圆桌 · 对齐轮 {round_num} · {group_name}]\n"
        f"你是 **{agent_name}**（@{agent_id}）。{role_hint}\n\n"
        f"{DISCUSS_PROMPT_HINT}\n\n"
        f"{_roundtable_topic_block(agenda)}\n\n"
        f"## 群聊上下文\n{group_context}\n\n"
        f"## 主持人上一轮汇总（要点）\n{fac_block}\n\n"
        f"## 各角色立论/对齐要点摘要\n{conflicts}\n\n"
        "---\n\n"
        "主持人已汇总各角色观点。请基于汇总发表**对齐意见**（交叉验证理解，非橡皮图章）。要求：\n"
        "- 必须用 `## 对齐回应` 列出：针对汇总或他角色观点中**至少 2 条**具体条目，"
        "逐条写「原观点 → 我理解的表述 → 同意/修正/补充/仍反对 → 理由」\n"
        "- 若接受他人修正，说明理由；若仍不同意，说明底线与替代方案\n"
        "- 须说明汇总是否**仍充分覆盖用户话题**；若答偏须指出\n"
        f"{_ROUNDTABLE_CROSS_CHECK}\n"
        "- 需要时可补充检索到的新事实（WebSearch/WebFetch 等）\n"
        "- **不要重复**立论或主持汇总全文；不要 @ 其他 Agent，不要 JSON\n"
        "- **不要**写「待用户拍板」——该内容仅在全部轮次用尽后由主持人整理\n"
        "- 仅输出你本轮的发言内容"
    )


def _build_facilitator_prompt(
    group_name: str,
    facilitator_name: str,
    facilitator_id: str,
    agenda: str,
    transcript: str,
    group_context: str,
    *,
    round_num: int,
    max_rounds: int,
    is_final: bool,
) -> str:
    prior = transcript.strip() or "（暂无）"
    if is_final:
        final_note = (
            "这是最后一轮汇总。必须输出 `## 对用户话题的回答`、`## 已共识`、"
            "`## 仍存分歧（需用户拍板）`；"
            "若未达成完全共识，必须额外输出 `## 保守方案`（在现有分歧下可执行的最小路径）。"
            "若讨论已偏离用户话题，在 `## 对用户话题的回答` 中说明并尽量拉回。"
            "末尾写 `CONSENSUS: AWAIT_USER`。"
        )
    elif round_num == 1:
        final_note = (
            "这是第一轮主持汇总（立论后、对齐轮前）。请客观整理各角色**对用户话题**的观点，输出："
            "`## 对用户话题的当前回答（草案）`、`## 各角色观点摘要`、`## 共同点`、"
            "`## 待对齐的差异`、`## 理解分歧清单`（各角色对同一概念理解是否一致）、"
            "`## 话题覆盖自检`（是否答偏/遗漏）。"
            "末尾**必须**写 `CONSENSUS: NEED_MORE`——须等全员对齐轮回应后再判定。"
            "不要替未发言/缺席成员补充观点，在汇总中标注「未参与」即可。"
            "**不要**写「待用户拍板」或「保守方案」（那是终局轮次的事）。"
        )
    else:
        final_note = (
            "对齐轮结束后将由你另发「最佳实践草案」并进入全员确认投票；"
            "本轮汇总输出：`## 对用户话题的当前回答（草案）`、`## 各角色观点摘要`、"
            "`## 共同点`、`## 待对齐的差异`、`## 理解分歧清单`、`## 话题覆盖自检`。"
            "末尾**必须**写 `CONSENSUS: NEED_MORE`（即使方向一致）。"
            "不要替未发言/缺席成员补充观点，在汇总中标注「未参与」即可。"
            "**不要**写「待用户拍板」或「保守方案」。"
        )
    return (
        f"[群组圆桌 · 主持汇总 · 第 {round_num}/{max_rounds} 轮 · {group_name}]\n"
        f"你是主持人 **{facilitator_name}**（@{facilitator_id}）。\n\n"
        f"{DISCUSS_PROMPT_HINT}\n\n"
        f"{_roundtable_topic_block(agenda)}\n\n"
        f"## 群聊上下文\n{group_context}\n\n"
        f"## 各轮发言要点摘要（非全文，请综合提炼）\n{prior}\n\n"
        "---\n\n"
        "请以主持人身份**汇总各角色观点**（提炼对用户话题的共识与分歧，不是另起炉灶、"
        "不是替用户拍板、不是擅自换成无关议题）。输出结构：\n"
        "## 对用户话题的当前回答（草案）\n"
        "## 各角色观点摘要\n"
        "## 共同点\n"
        "## 待对齐的差异\n"
        "## 理解分歧清单\n"
        "## 话题覆盖自检\n"
        "## 可选下一步（非必须，勿喧宾夺主）\n\n"
        f"{final_note}\n"
        "- 不要 @ 其他 Agent，不要 JSON\n"
        "- 不要替标记为「未参与」的成员代写观点"
    )


def _build_facilitator_draft_prompt(
    group_name: str,
    facilitator_name: str,
    facilitator_id: str,
    agenda: str,
    transcript: str,
    group_context: str,
    *,
    round_num: int,
    is_final: bool,
) -> str:
    prior = transcript.strip() or "（暂无）"
    final_note = (
        "这是最后一轮草案：若仍无法形成可投票草案，写 `BEST_PRACTICE: NEED_MORE` "
        "（或 `CONSENSUS: NEED_MORE`）并输出 `## 保守方案`。"
    ) if is_final else (
        "若分歧仍大、无法形成可执行的最佳实践，写 `BEST_PRACTICE: NEED_MORE` "
        "（或 `CONSENSUS: NEED_MORE`）并说明原因。"
    )
    return (
        f"[群组圆桌 · 最佳实践草案 · 第 {round_num} 轮 · {group_name}]\n"
        f"你是主持人 **{facilitator_name}**（@{facilitator_id}）。\n\n"
        f"{DISCUSS_PROMPT_HINT}\n\n"
        f"{_roundtable_topic_block(agenda)}\n\n"
        f"## 群聊上下文\n{group_context}\n\n"
        f"## 各轮要点摘要（含对齐回应，非全文）\n{prior}\n\n"
        "---\n\n"
        "全员对齐轮已结束。请基于讨论与对齐，发布**针对本话题的最佳实践**供确认投票。输出结构：\n"
        "## 问题界定\n"
        "## 推荐做法（本题最佳实践）\n"
        "## 多专业交叉验证\n"
        "（表格：角色 | 验证了什么 | 前提/残留风险；须覆盖每位已参与角色）\n"
        "## 未达成共识（如有）\n"
        "## 不适用 / 反模式\n"
        "## 话题覆盖自检\n"
        "## 可选下一步（非必须，勿喧宾夺主）\n\n"
        "若**话题覆盖自检**为已覆盖，且草案充分回答用户话题、可供全员交叉确认，"
        "末尾单独一行写 `BEST_PRACTICE: PROPOSED`（兼容旧格式可写 `CONSENSUS: PROPOSED`）；"
        f"否则写 `BEST_PRACTICE: NEED_MORE`。\n{final_note}\n"
        "- 投票规则：各角色对「最佳实践是否充分回答用户话题」表态；"
        "同意票 > 反对票 且 同意票 ≥ 半数则通过（少数服从多数）\n"
        "- 不要 @ 其他 Agent，不要 JSON\n"
        "- 草案须具体可执行，避免空泛口号；勿将讨论带离用户话题"
    )


def _build_consensus_confirm_prompt(
    group_name: str,
    agent_id: str,
    agent_name: str,
    role_hint: str,
    agenda: str,
    consensus_draft: str,
    group_context: str,
    *,
    round_num: int,
) -> str:
    return (
        f"[群组圆桌 · 最佳实践确认 · 第 {round_num} 轮 · {group_name}]\n"
        f"你是 **{agent_name}**（@{agent_id}）。{role_hint}\n\n"
        f"{DISCUSS_PROMPT_HINT}\n\n"
        f"{_roundtable_topic_block(agenda)}\n\n"
        f"## 群聊上下文\n{group_context}\n\n"
        f"## 主持人最佳实践草案\n{consensus_draft}\n\n"
        "---\n\n"
        "请对最佳实践草案表态——核心问题是：**当前最佳实践是否充分、正确地回答了用户话题？**"
        "（多专业交叉验证的终审，不是对主持文案的形式点头。）要求：\n"
        "- 末尾**单独一行**写 `CONSENSUS_VOTE: AGREE`（同意）/ `OBJECT`（反对）/ `ABSTAIN`（弃权）\n"
        "  也可写中文：`CONSENSUS_VOTE: 同意/反对/弃权`\n"
        "- **投票规则**：同意票 > 反对票 且 同意票 ≥ 半数则通过（少数服从多数）\n"
        "- 须含 `## 对用户话题的覆盖判断`（已覆盖 / 部分覆盖 / 未覆盖 + 说明）\n"
        "- 须含 `## 本专业交叉验证`（依据、风险、待验证项至少 1 条）\n"
        "- 若投 **反对**：说明用户话题哪一块未覆盖，或本专业仍不能接受什么（`## 反对理由`）；"
        "须指向草案中的具体条目\n"
        "- 若投 **同意**：说明为何认为最佳实践已充分回答话题；若仍有残留风险须写明\n"
        "- 若投 **弃权**：说明缺什么信息无法判断\n"
        "- 不要 @ 其他 Agent，不要 JSON\n"
        "- 仅输出你本轮的表态内容"
    )


def _build_objection_alignment_prompt(
    group_name: str,
    agent_id: str,
    agent_name: str,
    role_hint: str,
    agenda: str,
    consensus_draft: str,
    objections_summary: str,
    transcript: str,
    group_context: str,
    *,
    round_num: int,
) -> str:
    prior = transcript.strip() or "（暂无）"
    return (
        f"[群组圆桌 · 分歧交锋 · 第 {round_num} 轮 · {group_name}]\n"
        f"你是 **{agent_name}**（@{agent_id}）。{role_hint}\n\n"
        f"{DISCUSS_PROMPT_HINT}\n\n"
        f"{_roundtable_topic_block(agenda)}\n\n"
        f"## 群聊上下文\n{group_context}\n\n"
        f"## 最佳实践草案（未通过确认）\n{consensus_draft}\n\n"
        f"## 反对意见汇总\n{objections_summary}\n\n"
        f"## 完整讨论记录\n{prior}\n\n"
        "---\n\n"
        "最佳实践确认未通过（草案尚未被多数接受）。"
        "请针对反对意见与未解分歧发表**交锋回应**（须指向草案具体条目）：\n"
        "- 若你是反对者：坚持或修正立场，给出可接受的替代方案，说明用户话题哪块仍需补全\n"
        "- 若你曾同意：回应反对点，说明是否仍支持草案或建议如何修订以更好回答话题\n"
        f"{_ROUNDTABLE_CROSS_CHECK}\n"
        "- 不要重复全文；不要 @ 其他 Agent，不要 JSON\n"
        "- 仅输出你本轮的发言内容"
    )


def _record_roundtable_turn_failure(
    group_id: str,
    msg_id: str,
    agent_id: str,
    phase: str,
    round_num: int,
    error_code: str,
    detail: str,
    *,
    project_id: str,
    emit: Callable[[dict], None] | None,
) -> None:
    from common.roundtable_runtime import append_turn_failure_message

    append_turn_failure_message(
        _append_group_message,
        group_id=group_id,
        msg_id=msg_id,
        agent_id=agent_id,
        phase=phase,
        round_num=round_num,
        error_code=error_code,
        detail=detail,
        project_id=project_id,
    )
    if emit:
        emit({
            "event": "roundtable_turn_failed",
            "data": {
                "msg_id": msg_id,
                "agent_id": agent_id,
                "phase": phase,
                "round": round_num,
                "error_code": error_code,
                "message": detail,
            },
        })
        emit({"event": "error", "data": {"message": detail, "agent_id": agent_id}})


def _roundtable_stored_text(text: str) -> str:
    limit = _group_reply_preview_limit()
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit]


def _roundtable_agent_message_entry(
    *,
    agent_id: str,
    msg_id: str,
    text: str,
    phase: str,
    round_num: int,
    trace_parts: list | None,
    turn_meta: dict,
) -> dict:
    entry: dict = {
        "id": f"m_{int(time.time()*1000000)}_{agent_id}",
        "sender": agent_id,
        "text": _roundtable_stored_text(text),
        "timestamp": time.time(),
        "mentions": [],
        "in_reply_to": msg_id,
        "roundtable": True,
        "roundtable_phase": phase,
        "roundtable_round": round_num,
        "turn_meta": turn_meta,
    }
    if trace_parts:
        entry["thinking"] = trace_parts
    return entry


def _append_group_message(
    group_id: str,
    entry: dict,
    *,
    project_id: str = "",
    persist: bool = True,
) -> None:
    with _lock:
        groups = _load_groups()
        if group_id in groups:
            groups[group_id].setdefault("messages", []).append(entry)
            _save_groups(groups)
    if persist:
        try:
            from common.group_message_store import persist_group_message_entry

            persist_group_message_entry(group_id, entry, project_id=project_id)
        except Exception:
            pass


def _execute_roundtable_agent_turn(
    group_id: str,
    g: dict,
    sender: str,
    msg_id: str,
    agent_id: str,
    prompt: str,
    agents_info: dict,
    cancel_event,
    *,
    project_id: str,
    phase: str,
    round_num: int,
    turn_index: int,
    turn_total: int,
    publish: bool = True,
) -> tuple[bool, str]:
    """执行单轮圆桌发言（可并行调用），写入群消息并可选 fanout 事件。"""
    from hub.services.group_broadcast import publish as publish_group

    def _emit(evt: dict) -> None:
        if publish:
            publish_group(group_id, evt)

    _emit({"event": "roundtable_round", "data": {
        "msg_id": msg_id,
        "round": round_num,
        "phase": phase,
        "agent_id": agent_id,
    }})
    _emit({"event": "roundtable_turn", "data": {
        "agent_id": agent_id,
        "index": turn_index,
        "total": turn_total,
        "round": round_num,
        "phase": phase,
    }})
    _emit({"event": "routing", "data": {
        "to": agent_id,
        "from": sender,
        "message": prompt,
        "mode": "roundtable",
        "round": round_num,
        "phase": phase,
    }})

    from common.roundtable_runtime import collect_roundtable_reply

    result = collect_roundtable_reply(
        agent_id,
        prompt,
        cancel_event,
        group_id=group_id,
        project_id=project_id,
        reply_to_msg_id=msg_id,
        fanout_done=False,
        is_invalid_reply=is_invalid_roundtable_reply,
    )
    turn_meta_base = {
        "phase": phase,
        "round": round_num,
        "duration_ms": result.duration_ms,
    }
    if not result.ok:
        partial = (result.partial_text or "").strip()
        if not partial and result.error_code:
            partial = f"（发言失败 · {result.error_code}）"
        _append_group_message(
            group_id,
            _roundtable_agent_message_entry(
                agent_id=agent_id,
                msg_id=msg_id,
                text=partial,
                phase=phase,
                round_num=round_num,
                trace_parts=result.parts or None,
                turn_meta={
                    **turn_meta_base,
                    "status": "failed",
                    "error_code": result.error_code or "STREAM_ERROR",
                },
            ),
            project_id=project_id,
        )
        _record_roundtable_turn_failure(
            group_id,
            msg_id,
            agent_id,
            phase,
            round_num,
            result.error_code or "STREAM_ERROR",
            result.error_message or result.text,
            project_id=project_id,
            emit=_emit,
        )
        _emit({"event": "agent_done", "data": {
            "agent_id": agent_id,
            "reply_to": msg_id,
            "mode": "roundtable",
            "round": round_num,
            "phase": phase,
            "status": "failed",
            "error_code": result.error_code or "STREAM_ERROR",
        }})
        return False, result.error_message or result.text

    from common.roundtable_runtime import sanitize_roundtable_public_text

    reply = sanitize_roundtable_public_text(result.text)
    _append_group_message(
        group_id,
        _roundtable_agent_message_entry(
            agent_id=agent_id,
            msg_id=msg_id,
            text=reply,
            phase=phase,
            round_num=round_num,
            trace_parts=result.parts or None,
            turn_meta={**turn_meta_base, "status": "ok"},
        ),
        project_id=project_id,
    )

    _emit({"event": "agent_done", "data": {
        "agent_id": agent_id,
        "reply_to": msg_id,
        "mode": "roundtable",
        "round": round_num,
        "phase": phase,
        "status": "ok",
    }})
    return True, reply


def _yield_roundtable_agent_turn(
    group_id: str,
    g: dict,
    sender: str,
    msg_id: str,
    agent_id: str,
    prompt: str,
    agents_info: dict,
    cancel_event,
    *,
    project_id: str,
    phase: str,
    round_num: int,
    turn_index: int,
    turn_total: int,
) -> Generator[dict, None, tuple[bool, str]]:
    """串行路径：yield 事件并执行单轮发言。"""
    yield {"event": "roundtable_round", "data": {
        "msg_id": msg_id,
        "round": round_num,
        "phase": phase,
        "agent_id": agent_id,
    }}
    yield {"event": "roundtable_turn", "data": {
        "agent_id": agent_id,
        "index": turn_index,
        "total": turn_total,
        "round": round_num,
        "phase": phase,
    }}
    yield {"event": "routing", "data": {
        "to": agent_id,
        "from": sender,
        "message": prompt,
        "mode": "roundtable",
        "round": round_num,
        "phase": phase,
    }}

    ok, reply = _execute_roundtable_agent_turn(
        group_id, g, sender, msg_id, agent_id, prompt, agents_info, cancel_event,
        project_id=project_id,
        phase=phase,
        round_num=round_num,
        turn_index=turn_index,
        turn_total=turn_total,
        publish=False,
    )
    if not ok:
        yield {
            "event": "roundtable_turn_failed",
            "data": {
                "msg_id": msg_id,
                "agent_id": agent_id,
                "phase": phase,
                "round": round_num,
                "message": reply,
            },
        }
        return (False, reply)
    yield {"event": "agent_done", "data": {
        "agent_id": agent_id,
        "reply_to": msg_id,
        "mode": "roundtable",
        "round": round_num,
        "phase": phase,
    }}
    return (True, reply)


def _append_roundtable_turn_transcript(
    transcript_lines: list[str],
    *,
    label: str,
    agent_id: str,
    agent_name: str,
    reply: str,
) -> None:
    transcript_lines.append(
        f"\n\n---\n\n## [{label}] {agent_name} (@{agent_id})\n\n{reply}\n",
    )


def _handle_roundtable_turn_result(
    transcript_lines: list[str],
    *,
    ok: bool,
    reply: str,
    agent_id: str,
    agents_info: dict,
    label: str,
    error_code: str = "",
) -> bool:
    """单轮发言结果：失败时记录原因，不代写、不中断整桌讨论。"""
    if ok:
        _append_roundtable_turn_transcript(
            transcript_lines,
            label=label,
            agent_id=agent_id,
            agent_name=agents_info.get(agent_id, agent_id),
            reply=reply,
        )
        return True
    from common.roundtable_runtime import format_failure_transcript_line

    transcript_lines.append(
        format_failure_transcript_line(
            label=f"未参与 · {label}",
            agent_id=agent_id,
            agent_name=agents_info.get(agent_id, agent_id),
            error_code=error_code or "FAILED",
            detail=reply or "（未参与）",
        )
    )
    return False


def _fresh_group_context(
    group_id: str,
    *,
    exclude_msg_id: str | None = None,
    compress: bool = False,
) -> str:
    with _lock:
        groups = _load_groups()
        g = groups.get(group_id) or {}
    ctx = format_group_context(g, exclude_msg_id=exclude_msg_id)
    if compress:
        from common.roundtable_context import compress_group_context_text

        return compress_group_context_text(ctx)
    return ctx


def _run_group_roundtable(
    group_id: str,
    g: dict,
    sender: str,
    text: str,
    msg_id: str,
    mentioned: list[str],
    members: list[str],
    cancel_event=None,
    *,
    project_id: str = "",
    rounds_override: int | None = None,
) -> Generator[dict, None, None]:
    """多轮圆桌：并行独立思考 → 顺序立论 → 主持汇总 → 对齐 → 共识。"""
    facilitator, max_rounds, participants = resolve_roundtable_settings(
        g, mentioned, rounds_override=rounds_override,
    )
    if not participants:
        yield {"event": "error", "data": {"message": "圆桌讨论需要至少一位参与者（除主持人外）"}}
        return

    agenda = extract_agenda(text, members, prior_agenda=latest_roundtable_agenda(group_id))
    agents_info = {a["id"]: a["name"] for a in scan_agents()}
    fac_name = agents_info.get(facilitator, facilitator)
    group_context = _fresh_group_context(group_id, exclude_msg_id=msg_id, compress=True)
    transcript_path = _roundtable_transcript_path(group_id, msg_id)
    transcript_lines = [
        "# 群组圆桌记录\n",
        f"群组: {g.get('name', group_id)}\n",
        f"议题: {agenda}\n",
        f"主持人: {fac_name} (@{facilitator})\n",
        f"配置轮数: {max_rounds}\n",
        "规则: 并行思考 · 顺序立论 · 主持汇总 · 对齐交锋 · 最佳实践草案 · 交叉确认投票 · 产出本题最佳实践\n",
    ]
    speakers = roundtable_speaker_order(participants, members)
    from common.roundtable_runtime import (
        classify_turn_error,
        flush_roundtable_transcript,
        roundtable_session_timeout_seconds,
        start_session_deadline_watch,
    )

    start_session_deadline_watch(
        cancel_event,
        roundtable_session_timeout_seconds(len(speakers), max_rounds),
    )

    def _record_turn(
        *,
        ok: bool,
        reply: str,
        agent_id: str,
        label: str,
    ) -> bool:
        participated = _handle_roundtable_turn_result(
            transcript_lines,
            ok=ok,
            reply=reply,
            agent_id=agent_id,
            agents_info=agents_info,
            label=label,
            error_code=classify_turn_error(reply) if not ok else "",
        )
        flush_roundtable_transcript(transcript_path, transcript_lines)
        return participated
    spoke: dict[str, bool] = {agent_id: False for agent_id in speakers}
    thinking_notes: dict[str, str] = {}
    last_facilitator_summary = ""
    consensus_status = "unknown"
    configured_max = max_rounds
    effective_max = max_rounds
    cycle = 0
    alignment_cycles_completed = 0
    consensus_confirm_attempts = 0
    last_consensus_draft = ""

    yield {"event": "roundtable_start", "data": {
        "msg_id": msg_id,
        "agenda": agenda,
        "speakers": speakers,
        "facilitator": facilitator,
        "max_rounds": max_rounds,
        "mode": "roundtable",
    }}

    # —— Phase 0: 并行独立思考（群可见）——
    yield {"event": "roundtable_phase", "data": {
        "msg_id": msg_id,
        "phase": "thinking",
        "speaker_count": len(speakers),
    }}

    def _thinking_job(agent_id: str, index: int) -> tuple[str, bool, str]:
        prompt = _build_roundtable_thinking_prompt(
            g.get("name", group_id),
            agent_id,
            agents_info.get(agent_id, agent_id),
            _roundtable_role_hint(agent_id, phase="thinking"),
            agenda,
            group_context,
        )
        ok, reply = _execute_roundtable_agent_turn(
            group_id, g, sender, msg_id, agent_id, prompt, agents_info, cancel_event,
            project_id=project_id,
            phase="thinking",
            round_num=0,
            turn_index=index + 1,
            turn_total=len(speakers),
            publish=True,
        )
        return agent_id, ok, reply

    workers = max(1, min(len(speakers), 8))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_thinking_job, agent_id, idx): agent_id
            for idx, agent_id in enumerate(speakers)
        }
        for fut in as_completed(futures):
            if cancel_event and cancel_event.is_set():
                flush_roundtable_transcript(transcript_path, transcript_lines)
                yield {"event": "roundtable_aborted", "data": {"msg_id": msg_id, "reason": "cancelled"}}
                yield {"event": "error", "data": {"message": "已取消"}}
                return
            agent_id, ok, reply = fut.result()
            if ok:
                thinking_notes[agent_id] = reply
            _record_turn(
                ok=ok,
                reply=reply,
                agent_id=agent_id,
                label="独立思考",
            )

    # —— Phase 1: 立论轮（顺序发言）——
    for index, agent_id in enumerate(speakers):
        if cancel_event and cancel_event.is_set():
            flush_roundtable_transcript(transcript_path, transcript_lines)
            yield {"event": "roundtable_aborted", "data": {"msg_id": msg_id, "reason": "cancelled"}}
            yield {"event": "error", "data": {"message": "已取消"}}
            return
        prior = _roundtable_prior(transcript_lines)
        ctx = _fresh_group_context(group_id, exclude_msg_id=msg_id, compress=True)
        prompt = _build_roundtable_opening_prompt(
            g.get("name", group_id),
            agent_id,
            agents_info.get(agent_id, agent_id),
            _roundtable_role_hint(agent_id, phase="opening"),
            agenda,
            prior,
            ctx,
            thinking_notes.get(agent_id, ""),
        )
        gen = _yield_roundtable_agent_turn(
            group_id, g, sender, msg_id, agent_id, prompt, agents_info,
            cancel_event, project_id=project_id,
            phase="opening", round_num=1,
            turn_index=index + 1, turn_total=len(speakers),
        )
        try:
            while True:
                evt = next(gen)
                yield evt
        except StopIteration as stop:
            ok, reply = stop.value or (False, "未知错误")
            if ok:
                spoke[agent_id] = True
            _record_turn(ok=ok, reply=reply, agent_id=agent_id, label="立论")

    # —— Phase 2+: 主持汇总 + 对齐轮（可突破配置轮数，严格触发）——
    while cycle < effective_max:
        cycle += 1
        if cancel_event and cancel_event.is_set():
            flush_roundtable_transcript(transcript_path, transcript_lines)
            yield {"event": "roundtable_aborted", "data": {"msg_id": msg_id, "reason": "cancelled"}}
            yield {"event": "error", "data": {"message": "已取消"}}
            return

        is_final = cycle >= effective_max
        prior = _roundtable_prior(transcript_lines)
        ctx = _fresh_group_context(group_id, exclude_msg_id=msg_id, compress=True)
        fac_prompt = _build_facilitator_prompt(
            g.get("name", group_id),
            fac_name,
            facilitator,
            agenda,
            prior,
            ctx,
            round_num=cycle,
            max_rounds=effective_max,
            is_final=is_final,
        )
        gen = _yield_roundtable_agent_turn(
            group_id, g, sender, msg_id, facilitator, fac_prompt, agents_info,
            cancel_event, project_id=project_id,
            phase="consensus" if is_final else "facilitator",
            round_num=cycle,
            turn_index=1, turn_total=1,
        )
        try:
            while True:
                evt = next(gen)
                yield evt
        except StopIteration as stop:
            ok, reply = stop.value or (False, "未知错误")
            if ok:
                last_facilitator_summary = reply
            label = "共识" if is_final else f"主持汇总 R{cycle}"
            _record_turn(
                ok=ok,
                reply=reply if ok else reply,
                agent_id=facilitator,
                label=label,
            )

        if not ok:
            consensus_status = "await_user" if is_final else "need_more"
            if is_final:
                break
            continue

        consensus_status = parse_consensus_status(reply)
        if consensus_status == "yes":
            consensus_status = "need_more"

        if is_final:
            try:
                from common.skill_settings import group_discussion_auto_finalize_on_max_rounds

                auto_finalize = group_discussion_auto_finalize_on_max_rounds()
            except Exception:
                auto_finalize = True
            if auto_finalize:
                consensus_status = "await_user"
                break

        # 对齐轮（交锋=对齐+回应；至少完成一轮后才可进入共识草案）
        yield {"event": "roundtable_phase", "data": {
            "msg_id": msg_id,
            "phase": "alignment",
            "speaker_count": len(speakers),
            "round": cycle,
        }}
        for index, agent_id in enumerate(speakers):
            if cancel_event and cancel_event.is_set():
                flush_roundtable_transcript(transcript_path, transcript_lines)
                yield {"event": "roundtable_aborted", "data": {"msg_id": msg_id, "reason": "cancelled"}}
                yield {"event": "error", "data": {"message": "已取消"}}
                return
            prior = _roundtable_prior(transcript_lines)
            conflict_digest = _roundtable_prior(transcript_lines, mode="conflicts")
            ctx = _fresh_group_context(group_id, exclude_msg_id=msg_id, compress=True)
            prompt = _build_roundtable_alignment_prompt(
                g.get("name", group_id),
                agent_id,
                agents_info.get(agent_id, agent_id),
                _roundtable_role_hint(agent_id, phase="alignment"),
                agenda,
                last_facilitator_summary,
                conflict_digest,
                ctx,
                round_num=cycle,
            )
            gen = _yield_roundtable_agent_turn(
                group_id, g, sender, msg_id, agent_id, prompt, agents_info,
                cancel_event, project_id=project_id,
                phase="alignment", round_num=cycle + 1,
                turn_index=index + 1, turn_total=len(speakers),
            )
            try:
                while True:
                    evt = next(gen)
                    yield evt
            except StopIteration as stop:
                ok, reply = stop.value or (False, "未知错误")
                if ok:
                    spoke[agent_id] = True
                _record_turn(
                    ok=ok,
                    reply=reply,
                    agent_id=agent_id,
                    label=f"对齐 R{cycle + 1}",
                )

        alignment_cycles_completed += 1

        # —— 共识草案 + 确认投票 ——
        if alignment_cycles_completed >= MIN_ALIGNMENT_CYCLES_BEFORE_EARLY_CONSENSUS:
            if cancel_event and cancel_event.is_set():
                flush_roundtable_transcript(transcript_path, transcript_lines)
                yield {"event": "roundtable_aborted", "data": {"msg_id": msg_id, "reason": "cancelled"}}
                yield {"event": "error", "data": {"message": "已取消"}}
                return

            prior = _roundtable_prior(transcript_lines)
            ctx = _fresh_group_context(group_id, exclude_msg_id=msg_id, compress=True)
            draft_prompt = _build_facilitator_draft_prompt(
                g.get("name", group_id),
                fac_name,
                facilitator,
                agenda,
                prior,
                ctx,
                round_num=cycle,
                is_final=is_final,
            )
            gen = _yield_roundtable_agent_turn(
                group_id, g, sender, msg_id, facilitator, draft_prompt, agents_info,
                cancel_event, project_id=project_id,
                phase="consensus_draft",
                round_num=cycle,
                turn_index=1, turn_total=1,
            )
            try:
                while True:
                    evt = next(gen)
                    yield evt
            except StopIteration as stop:
                draft_ok, draft_reply = stop.value or (False, "未知错误")
                _record_turn(
                    ok=draft_ok,
                    reply=draft_reply if draft_ok else draft_reply,
                    agent_id=facilitator,
                    label=f"最佳实践草案 R{cycle}",
                )

            if not draft_ok:
                consensus_status = "need_more"
                if is_final:
                    break
            else:
                last_consensus_draft = draft_reply
                draft_status = parse_facilitator_draft_status(draft_reply)
                if draft_status == "proposed" and consensus_confirm_attempts < MAX_CONSENSUS_CONFIRM_ATTEMPTS:
                    consensus_confirm_attempts += 1
                    yield {"event": "roundtable_phase", "data": {
                        "msg_id": msg_id,
                        "phase": "consensus_confirm",
                        "speaker_count": len(speakers),
                        "round": cycle,
                    }}
                    votes: dict[str, str] = {}
                    vote_replies: dict[str, str] = {}
                    for index, agent_id in enumerate(speakers):
                        if cancel_event and cancel_event.is_set():
                            flush_roundtable_transcript(transcript_path, transcript_lines)
                            yield {"event": "roundtable_aborted", "data": {"msg_id": msg_id, "reason": "cancelled"}}
                            yield {"event": "error", "data": {"message": "已取消"}}
                            return
                        ctx = _fresh_group_context(group_id, exclude_msg_id=msg_id, compress=True)
                        confirm_prompt = _build_consensus_confirm_prompt(
                            g.get("name", group_id),
                            agent_id,
                            agents_info.get(agent_id, agent_id),
                            _roundtable_role_hint(agent_id, phase="consensus_confirm"),
                            agenda,
                            draft_reply,
                            ctx,
                            round_num=cycle,
                        )
                        gen = _yield_roundtable_agent_turn(
                            group_id, g, sender, msg_id, agent_id, confirm_prompt,
                            agents_info, cancel_event, project_id=project_id,
                            phase="consensus_confirm",
                            round_num=cycle,
                            turn_index=index + 1,
                            turn_total=len(speakers),
                        )
                        try:
                            while True:
                                evt = next(gen)
                                yield evt
                        except StopIteration as stop:
                            c_ok, c_reply = stop.value or (False, "未知错误")
                            if c_ok:
                                spoke[agent_id] = True
                                votes[agent_id] = parse_consensus_vote(c_reply)
                                vote_replies[agent_id] = c_reply
                            else:
                                votes[agent_id] = "unknown"
                                vote_replies[agent_id] = c_reply
                            vote_label = votes.get(agent_id, "unknown")
                            _record_turn(
                                ok=c_ok,
                                reply=c_reply,
                                agent_id=agent_id,
                                label=f"最佳实践确认·{vote_label} R{cycle}",
                            )

                    if consensus_confirm_passed(votes, speakers):
                        consensus_status = "yes"
                        stats = consensus_vote_stats(votes, speakers)
                        threshold = consensus_majority_threshold(len(speakers))
                        minority_note = (
                            f"，反对 {stats['object']} 票（少数服从多数，草案通过）"
                            if stats["object"] else "，无反对票"
                        )
                        transcript_lines.append(
                            f"\n\n---\n\n## [系统] 最佳实践确认通过\n\n"
                            f"各角色确认：当前最佳实践**充分回答用户话题**。"
                            f"同意 {stats['agree']}/{len(speakers)}"
                            f"{minority_note}（阈值 ≥ {threshold}）。\n",
                        )
                        break

                    consensus_status = "need_more"
                    objection_block = format_consensus_objections(
                        votes, vote_replies, agents_info,
                    )
                    transcript_lines.append(f"\n\n---\n\n{objection_block}\n")
                    last_facilitator_summary = objection_block

                    if is_final:
                        break

                    # 分歧交锋：全员回应反对意见
                    yield {"event": "roundtable_phase", "data": {
                        "msg_id": msg_id,
                        "phase": "objection",
                        "speaker_count": len(speakers),
                        "round": cycle,
                    }}
                    prior = _roundtable_prior(transcript_lines)
                    ctx = _fresh_group_context(group_id, exclude_msg_id=msg_id, compress=True)
                    for index, agent_id in enumerate(speakers):
                        if cancel_event and cancel_event.is_set():
                            flush_roundtable_transcript(transcript_path, transcript_lines)
                            yield {"event": "roundtable_aborted", "data": {"msg_id": msg_id, "reason": "cancelled"}}
                            yield {"event": "error", "data": {"message": "已取消"}}
                            return
                        obj_prompt = _build_objection_alignment_prompt(
                            g.get("name", group_id),
                            agent_id,
                            agents_info.get(agent_id, agent_id),
                            _roundtable_role_hint(agent_id, phase="alignment"),
                            agenda,
                            draft_reply,
                            objection_block,
                            prior,
                            ctx,
                            round_num=cycle,
                        )
                        gen = _yield_roundtable_agent_turn(
                            group_id, g, sender, msg_id, agent_id, obj_prompt,
                            agents_info, cancel_event, project_id=project_id,
                            phase="objection",
                            round_num=cycle + 1,
                            turn_index=index + 1,
                            turn_total=len(speakers),
                        )
                        try:
                            while True:
                                evt = next(gen)
                                yield evt
                        except StopIteration as stop:
                            o_ok, o_reply = stop.value or (False, "未知错误")
                            if o_ok:
                                spoke[agent_id] = True
                            _record_turn(
                                ok=o_ok,
                                reply=o_reply,
                                agent_id=agent_id,
                                label=f"分歧交锋 R{cycle + 1}",
                            )
                    alignment_cycles_completed += 1
                    continue

                consensus_status = "need_more"
                if is_final:
                    break

        if consensus_status == "yes":
            break

        if should_extend_roundtable_cycles(
            consensus_status=consensus_status,
            cycle=cycle,
            configured_max=configured_max,
            effective_max=effective_max,
            spoke=spoke,
        ):
            effective_max = min(effective_max + 1, max_roundtable_rounds_cap())
            transcript_lines.append(
                f"\n\n---\n\n## [系统] 轮次扩展\n\n"
                f"已达配置 {configured_max} 轮且 CONSENSUS: NEED_MORE，"
                f"参与率 {roundtable_participation_rate(spoke):.0%} ≥ 2/3，"
                f"扩展至第 {effective_max} 轮。\n",
            )
            is_final = False

    transcript_path = _roundtable_transcript_path(group_id, msg_id)
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    full_transcript = "".join(transcript_lines)
    transcript_path.write_text(full_transcript, encoding="utf-8")

    if consensus_status == "need_more" and cycle >= effective_max:
        consensus_status = "await_user"

    user_decision_summary = (last_consensus_draft or last_facilitator_summary or "").strip()

    assessment_rel_path = ""
    if consensus_status == "yes" and last_consensus_draft:
        from common.roundtable_runtime import write_best_practice_assessment

        assessment_agenda = agenda
        if _CONTINUE_AGENDA_RE.match(agenda.strip()):
            topic_match = re.search(
                r"用户话题为[「「](.+?)[」」]",
                last_consensus_draft,
            )
            if topic_match:
                assessment_agenda = topic_match.group(1).strip()
            else:
                inherited = latest_roundtable_agenda(group_id)
                if inherited:
                    assessment_agenda = inherited

        assessment_path = write_best_practice_assessment(
            agenda=assessment_agenda,
            group_name=g.get("name", group_id),
            draft_text=last_consensus_draft,
            transcript_rel_path=to_relative_path(transcript_path),
            msg_id=msg_id,
        )
        if assessment_path is not None:
            assessment_rel_path = to_relative_path(assessment_path)
            try:
                from memstack.facade import on_consensus
                from memstack.orchestration.context import ConsensusContext

                on_consensus(
                    ConsensusContext(
                        group_id=group_id,
                        draft_text=last_consensus_draft,
                        agenda=assessment_agenda,
                    )
                )
            except Exception:
                pass

    if consensus_status == "yes":
        status_text = (
            f"圆桌已产出**本题最佳实践**（第 {cycle}/{configured_max} 轮，"
            f"交叉确认投票通过（少数服从多数），参与率 {roundtable_participation_rate(spoke):.0%}，"
            f"主持人 @{facilitator}）。终稿见下方摘要或 transcript。"
        )
        if assessment_rel_path:
            status_text += f"\n\n修正项汇总已写入：`{assessment_rel_path}`"
    elif consensus_status == "await_user":
        extended = effective_max > configured_max
        ext_note = f"，已扩展至 {effective_max} 轮" if extended else ""
        status_text = (
            f"圆桌已达 {configured_max} 轮上限（实际 {cycle} 轮{ext_note}），"
            f"最佳实践尚未完全确认。请查看 transcript 中「推荐做法 / 未达成共识」并拍板。"
            f"主持人 @{facilitator}。"
        )
    elif consensus_status == "need_more":
        extended = effective_max > configured_max
        ext_note = f"，已扩展至 {effective_max} 轮" if extended else ""
        status_text = (
            f"圆桌完成但最佳实践尚未完全确认（第 {cycle}/{configured_max} 轮{ext_note}），"
            f"已输出草案与分歧清单，请查看并拍板。主持人 @{facilitator}。"
        )
    else:
        status_text = f"圆桌讨论完成（{len(speakers)} 位参与，主持人 @{facilitator}）。"

    summary_entry = {
        "id": f"m_{int(time.time()*1000000)}_roundtable",
        "sender": "system",
        "text": status_text,
        "timestamp": time.time(),
        "mentions": [],
        "roundtable_transcript": to_relative_path(transcript_path),
        "roundtable_consensus": consensus_status,
        "roundtable_meta": {
            "artifact_type": "best_practice",
            "agenda": agenda[:500],
            "facilitator": facilitator,
            "participants": speakers,
            "cycles_run": cycle,
        },
    }
    if assessment_rel_path:
        summary_entry["roundtable_meta"]["assessment_path"] = assessment_rel_path
    if user_decision_summary:
        summary_entry["roundtable_user_decision_summary"] = user_decision_summary[:12000]
    _append_group_message(group_id, summary_entry, project_id=project_id, persist=True)

    yield {"event": "roundtable_done", "data": {
        "msg_id": msg_id,
        "speaker_count": len(speakers),
        "facilitator": facilitator,
        "max_rounds": configured_max,
        "effective_rounds": effective_max,
        "cycles_run": cycle,
        "participation_rate": round(roundtable_participation_rate(spoke), 3),
        "consensus": consensus_status,
        "artifact_type": "best_practice",
        "transcript_path": summary_entry["roundtable_transcript"],
        "assessment_path": assessment_rel_path or None,
    }}


def _group_reply_preview_limit() -> int:
    """群消息 Agent 回复预览长度；0 表示不截断。"""
    try:
        from store.skill_config import skill_config
        raw = skill_config.get("groups", "reply_preview_limit", default=0)
        return max(0, int(raw or 0))
    except Exception:
        return 0


def send_group_message(
    group_id: str,
    sender: str,    # "user" 或 agent_id
    text: str,
    cancel_event=None,
    route_mentions: bool | None = None,
    route_only: bool = False,
    mode: str | None = None,
    roundtable_rounds: int | None = None,
) -> Generator[dict, None, None]:
    """
    在群组中发送消息，自动处理 @mention 路由

    Args:
        group_id: 群组 ID
        sender: 发送者 ("user" 或 agent_id)
        text: 消息文本
        mode: 已废弃；始终按 @all→圆桌、@具体 Agent→群聊回复 自动判定。传 roundtable/notify 可强制覆盖。

    Yields:
        dict: 处理结果事件
    """
    groups = _load_groups()
    g = groups.get(group_id)
    if not g:
        yield {"event": "error", "data": {"message": "群组不存在"}}
        return

    members = g.get("members", [])
    project_id = str(g.get("project_id") or "")

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

    if sender == "user" and is_roundtable_terminate_command(text):
        msg_entry["mentions"] = mentioned
        yield {"event": "group_message", "data": {
            "msg_id": msg_id, "sender": sender, "text": text,
            "mentions": mentioned,
        }}
        with _lock:
            groups = _load_groups()
            if group_id in groups:
                groups[group_id].setdefault("messages", []).append(msg_entry)
                _save_groups(groups)
        try:
            from common.group_message_store import persist_group_message
            persist_group_message(group_id, sender, text, project_id=project_id)
        except Exception:
            pass

        from hub.services.chat_cancel import cancel_group_roundtable
        from hub.services.group_broadcast import publish as publish_group

        agent_members = [m for m in members if m != "user"]
        result = cancel_group_roundtable(group_id, agent_members)
        killed = result.get("killed_pids") or []
        if result.get("cancelled") or killed:
            kill_note = f"，已终止 {len(killed)} 个后台进程" if killed else ""
            sys_text = f"讨论已终止{kill_note}。可查看 transcript 了解当前进度。"
        else:
            sys_text = "当前无进行中的圆桌讨论。"

        sys_entry = {
            "id": f"m_{int(time.time()*1000000)}_terminated",
            "sender": "system",
            "text": sys_text,
            "timestamp": time.time(),
            "mentions": [],
            "roundtable_phase": "terminated",
        }
        _append_group_message(group_id, sys_entry, project_id=project_id, persist=True)

        aborted = {
            "event": "roundtable_aborted",
            "data": {
                "msg_id": msg_id,
                "reason": "user_terminate",
                "cancelled": bool(result.get("cancelled")),
                "killed_pids": killed,
            },
        }
        publish_group(group_id, aborted)
        yield aborted
        yield {"event": "group_message", "data": {
            "msg_id": sys_entry["id"],
            "sender": "system",
            "text": sys_text,
            "mentions": [],
        }}
        return

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
        try:
            from common.group_message_store import persist_group_message
            persist_group_message(
                group_id, sender, text,
                project_id=str(g.get("project_id") or ""),
            )
        except Exception:
            pass
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
    try:
        from common.group_message_store import persist_group_message
        persist_group_message(
            group_id, sender, text,
            project_id=str(g.get("project_id") or ""),
        )
    except Exception:
        pass

    # 仅用户 @mention 或显式 route_mentions 时触发 Agent 调度
    if route_mentions is None:
        route_mentions = sender == "user"
    if not route_mentions:
        return

    if mode in ("roundtable", "notify"):
        resolved_mode = mode
    else:
        resolved_mode = detect_group_mode(text, mentioned)

    if resolved_mode == "roundtable":
        from hub.services.chat_cancel import group_session_key, register_chat, unregister_chat
        from hub.services.group_broadcast import publish as publish_group

        session_key = group_session_key(group_id)
        bg_cancel = register_chat(session_key)

        def _bg_roundtable() -> None:
            try:
                with _lock:
                    groups_now = _load_groups()
                    g_now = groups_now.get(group_id) or g
                for evt in _run_group_roundtable(
                    group_id, g_now, sender, text, msg_id, mentioned, members,
                    bg_cancel, project_id=project_id,
                    rounds_override=roundtable_rounds,
                ):
                    publish_group(group_id, evt)
            finally:
                unregister_chat(session_key, bg_cancel)

        threading.Thread(
            target=_bg_roundtable,
            daemon=True,
            name=f"roundtable-{group_id}",
        ).start()
        yield {"event": "roundtable_detached", "data": {
            "msg_id": msg_id,
            "mode": "roundtable",
            "hint": "圆桌在后台继续；刷新页面不会中断，进度通过群事件推送。",
        }}
        return

    # @具体 Agent：群聊回复（同私聊逻辑，回复展示在群内）
    from hub.services.chat_cancel import group_session_key, register_chat, unregister_chat
    from hub.services.group_broadcast import publish as publish_group

    agents_info = {a["id"]: a["name"] for a in scan_agents()}
    sender_display = "用户" if sender == "user" else agents_info.get(sender, sender)
    group_ctx = _fresh_group_context(group_id, exclude_msg_id=msg_id)
    dispatch_jobs: list[tuple[str, str]] = []

    for agent_id in mentioned:
        msg_for_agent = _extract_message_for_agent(text, agent_id, members)
        context = (
            f"[群组: {g['name']}]\n"
            f"[来自: {sender_display}]\n\n"
            f"## 群聊上下文\n{group_ctx}\n\n"
            f"## 当前消息\n{msg_for_agent}\n\n"
            "用户在群里 @ 了你。请像私聊一样理解问题并回复；"
            "可结合群上下文与过往圆桌结论；回复会展示在本群。"
            "这是讨论模式，不是项目 workflow execute 派活。"
            "不要在回复中 @ 其他 Agent。"
        )
        dispatch_jobs.append((agent_id, context))

    if not dispatch_jobs:
        return

    session_key = group_session_key(group_id)
    bg_cancel = register_chat(session_key)

    def _bg_notify() -> None:
        try:
            threads: list[threading.Thread] = []

            def _run_one(agent_id: str, context: str) -> None:
                if bg_cancel.is_set():
                    return
                publish_group(group_id, {"event": "routing", "data": {
                    "to": agent_id,
                    "from": sender,
                    "message": context,
                }})
                for evt in _stream_agent_in_group(
                    group_id, agent_id, context, msg_id, bg_cancel, as_generator=True,
                ):
                    publish_group(group_id, evt)

            for agent_id, context in dispatch_jobs:
                t = threading.Thread(
                    target=_run_one,
                    args=(agent_id, context),
                    daemon=True,
                    name=f"notify-{group_id}-{agent_id}",
                )
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
        finally:
            unregister_chat(session_key, bg_cancel)

    threading.Thread(
        target=_bg_notify,
        daemon=True,
        name=f"notify-{group_id}",
    ).start()
    yield {"event": "notify_detached", "data": {
        "msg_id": msg_id,
        "agents": [a for a, _ in dispatch_jobs],
        "mode": "notify",
        "hint": "Agent 在后台回复；刷新页面不会中断，进度通过群事件推送。",
    }}


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
    from common.thinking_trace import append_thinking_sse

    reply_parts: list[str] = []
    trace_parts: list[dict] = []
    try:
        for sse_json in stream_chat(
            agent_id,
            context,
            cancel_event=cancel_event,
            group_id=group_id,
            memory_mode="group",
        ):
            if cancel_event and cancel_event.is_set():
                err = {"event": "error", "data": {"message": "已取消"}}
                if as_generator:
                    yield err
                return
            if not as_generator:
                fanout_stream_event(agent_id, sse_json, group_id=group_id)
            evt = json.loads(sse_json)
            append_thinking_sse(evt, reply_parts, trace_parts)
            thinking = _sse_to_thinking(evt)
            if thinking:
                out = {"event": "agent_thinking", "data": {
                    "agent_id": agent_id,
                    "reply_to": msg_id,
                    **thinking,
                }}
                if as_generator:
                    yield out
            elif evt.get("event") == "text":
                content = (evt.get("data") or {}).get("content", "") or ""
                if content and as_generator:
                    yield {"event": "agent_thinking", "data": {
                        "agent_id": agent_id,
                        "reply_to": msg_id,
                        "type": "text",
                        "content": content,
                    }}
            elif evt.get("event") == "done":
                data = evt.get("data") or {}
                summary = data.get("summary", "") or ""
                stored_text = "".join(reply_parts).strip() or summary or "已完成"
                limit = _group_reply_preview_limit()
                if limit > 0 and len(stored_text) > limit:
                    stored_text = stored_text[:limit]
                entry = {
                    "id": f"m_{int(time.time()*1000000)}_{agent_id}",
                    "sender": agent_id,
                    "text": stored_text,
                    "timestamp": time.time(),
                    "mentions": [],
                    "in_reply_to": msg_id,
                }
                if trace_parts:
                    entry["thinking"] = trace_parts
                _append_group_message(group_id, entry)

                done_evt = {"event": "agent_done", "data": {
                    "agent_id": agent_id,
                    "reply_to": msg_id,
                    "session_id": data.get("session_id", ""),
                }}
                if as_generator:
                    yield done_evt
                elif group_id:
                    from hub.services.group_broadcast import publish as publish_group
                    publish_group(group_id, done_evt)
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
    result = re.sub(r"@(?:all|everyone)\b", "", result, flags=re.IGNORECASE)
    result = result.replace(f"@{agent_id}", "").strip()
    for other in all_members:
        if other != agent_id:
            result = result.replace(f"@{other}", "").strip()
    return result or text