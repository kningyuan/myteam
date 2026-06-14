#!/usr/bin/env python3
"""群消息同步至 Store conversation/message（Phase 4）+ 可选 Store 读回。"""
from __future__ import annotations

import copy
import logging
import os
import time
from typing import Any, Optional

logger = logging.getLogger("group_message_store")


def hub_group_read_store_enabled() -> bool:
    """MYTEAM_HUB_GROUP_READ_STORE=1 时启用 Store 读回/合并。"""
    return os.environ.get("MYTEAM_HUB_GROUP_READ_STORE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _conversation_id(group_id: str) -> str:
    return f"group:{group_id}"


def _store_row_to_group_message(row: dict) -> Optional[dict]:
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    entry = meta.get("group_entry")
    if isinstance(entry, dict) and entry.get("id"):
        out = copy.deepcopy(entry)
        if not out.get("text") and row.get("text"):
            out["text"] = row["text"]
        return out
    msg_id = meta.get("group_message_id") or f"m_store_{row.get('id', 0)}"
    sender = str(row.get("author") or meta.get("sender") or "")
    if not sender and row.get("role") == "user":
        sender = "user"
    created = row.get("created_at")
    ts = float(created) if isinstance(created, (int, float)) else time.time()
    out: dict[str, Any] = {
        "id": str(msg_id),
        "sender": sender,
        "text": str(row.get("text") or ""),
        "timestamp": ts,
        "mentions": meta.get("mentions") if isinstance(meta.get("mentions"), list) else [],
    }
    if meta.get("in_reply_to"):
        out["in_reply_to"] = meta["in_reply_to"]
    if isinstance(meta.get("thinking"), list) and meta["thinking"]:
        out["thinking"] = meta["thinking"]
    for key in (
        "roundtable",
        "roundtable_phase",
        "roundtable_round",
        "turn_meta",
        "roundtable_consensus",
        "roundtable_transcript",
        "roundtable_user_decision_summary",
        "roundtable_meta",
    ):
        if key in meta:
            out[key] = meta[key]
    return out


def list_group_messages_from_store(group_id: str, *, limit: int = 50) -> list[dict]:
    if not group_id or limit <= 0:
        return []
    try:
        from common.store import Store

        store = Store()
        rows = store.recent_messages(_conversation_id(group_id), limit)
        out: list[dict] = []
        for row in rows:
            msg = _store_row_to_group_message(row)
            if msg:
                out.append(msg)
        return out
    except Exception as e:
        logger.debug("list_group_messages_from_store skipped: %s", e)
        return []


def _index_store_by_id(store_msgs: list[dict]) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for m in store_msgs:
        mid = str(m.get("id") or "")
        if mid:
            by_id[mid] = m
    return by_id


def _index_store_thinking(store_msgs: list[dict]) -> dict[str, list]:
    """key = in_reply_to:sender → thinking[]"""
    out: dict[str, list] = {}
    for m in store_msgs:
        thinking = m.get("thinking")
        reply = m.get("in_reply_to")
        sender = m.get("sender")
        if (
            isinstance(thinking, list)
            and thinking
            and reply
            and sender not in (None, "user", "system")
        ):
            out[f"{reply}:{sender}"] = thinking
    return out


def merge_json_messages_with_store(
    json_messages: list[dict],
    store_messages: list[dict],
) -> list[dict]:
    """以 groups.json 为结构真相，从 Store 叠加 thinking / 缺失字段。"""
    if not json_messages:
        return store_messages[-50:] if store_messages else []
    if not store_messages:
        return json_messages

    by_id = _index_store_by_id(store_messages)
    thinking_by_turn = _index_store_thinking(store_messages)
    merged: list[dict] = []
    for raw in json_messages:
        m = copy.deepcopy(raw) if isinstance(raw, dict) else {}
        mid = str(m.get("id") or "")
        store_match = by_id.get(mid)
        if store_match:
            if not m.get("thinking") and store_match.get("thinking"):
                m["thinking"] = store_match["thinking"]
            for key in (
                "turn_meta",
                "roundtable_phase",
                "roundtable_round",
                "roundtable",
                "roundtable_consensus",
                "roundtable_transcript",
                "roundtable_user_decision_summary",
                "roundtable_meta",
            ):
                if key not in m and key in store_match:
                    m[key] = store_match[key]
        elif not m.get("thinking"):
            reply = m.get("in_reply_to")
            sender = m.get("sender")
            if reply and sender not in (None, "user", "system"):
                turn_key = f"{reply}:{sender}"
                if turn_key in thinking_by_turn:
                    m["thinking"] = thinking_by_turn[turn_key]
        merged.append(m)
    return merged


def _store_has_full_entries(store_messages: list[dict]) -> bool:
    if not store_messages:
        return False
    with_entry = sum(
        1 for m in store_messages if str(m.get("id") or "").startswith("m_")
    )
    return with_entry >= max(1, len(store_messages) // 2)


def resolve_group_messages_for_api(
    group_id: str,
    json_messages: list[dict],
    *,
    limit: int = 50,
) -> list[dict]:
    """GET /api/groups/{id} 的消息列表解析。"""
    recent_json = list(json_messages or [])[-limit:]
    if not hub_group_read_store_enabled():
        return recent_json

    store_msgs = list_group_messages_from_store(group_id, limit=limit)
    if not store_msgs:
        return recent_json

    if _store_has_full_entries(store_msgs) and len(store_msgs) >= len(recent_json):
        return store_msgs[-limit:]

    return merge_json_messages_with_store(recent_json, store_msgs)


def persist_group_message(
    group_id: str,
    sender: str,
    text: str,
    *,
    project_id: str = "",
    thinking: list | None = None,
    in_reply_to: str = "",
    entry: dict | None = None,
) -> None:
    """双写：groups.json 仍保留；新消息同时写入 SQLite。"""
    if entry is None:
        if not group_id or not text:
            return
        entry = {
            "id": f"m_{int(time.time() * 1000000)}",
            "sender": sender,
            "text": text,
            "timestamp": time.time(),
            "mentions": [],
        }
        if thinking:
            entry["thinking"] = thinking
        if in_reply_to:
            entry["in_reply_to"] = in_reply_to
    elif not group_id:
        return
    else:
        sender = str(entry.get("sender") or sender or "")
        text = str(entry.get("text") or text or "")

    try:
        from common.store import Store

        store = Store()
        cid = _conversation_id(group_id)
        store.create_conversation(
            cid,
            kind="group",
            participants=[],
            project_id=project_id or None,
            title=group_id,
        )
        role = "user" if sender == "user" else "agent"
        meta: dict[str, Any] = {
            "group_id": group_id,
            "group_entry": copy.deepcopy(entry),
            "group_message_id": str(entry.get("id") or ""),
            "sender": sender,
        }
        if entry.get("thinking"):
            meta["thinking"] = entry["thinking"]
        if entry.get("in_reply_to"):
            meta["in_reply_to"] = entry["in_reply_to"]
        for key in (
            "mentions",
            "roundtable",
            "roundtable_phase",
            "roundtable_round",
            "turn_meta",
        ):
            if key in entry:
                meta[key] = entry[key]
        store.append_message(cid, role, sender, text=text, meta=meta)
    except Exception as e:
        logger.debug("persist_group_message skipped: %s", e)


def persist_group_message_entry(
    group_id: str,
    entry: dict,
    *,
    project_id: str = "",
) -> None:
    persist_group_message(
        group_id,
        str(entry.get("sender") or ""),
        str(entry.get("text") or ""),
        project_id=project_id,
        entry=entry,
    )
