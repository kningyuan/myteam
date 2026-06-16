"""对话归档 — 删除/隐藏/检索恢复私聊窗口。"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional

from hub.paths import CHAT_ARCHIVES_DIR

_lock = threading.Lock()
_INDEX_FILE = CHAT_ARCHIVES_DIR / "index.json"


def _load_index() -> dict:
    try:
        if _INDEX_FILE.exists():
            with open(_INDEX_FILE, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"hidden": {}, "archives": {}}


def _save_index(data: dict):
    CHAT_ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
    with open(_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def hide_chat(agent_id: str, snapshot: Optional[dict] = None) -> dict:
    """从侧栏隐藏对话；可选保存消息快照供检索。"""
    with _lock:
        idx = _load_index()
        entry = {
            "agent_id": agent_id,
            "hidden_at": time.time(),
            "label": (snapshot or {}).get("label", agent_id),
        }
        if snapshot and snapshot.get("messages"):
            archive_path = CHAT_ARCHIVES_DIR / f"{agent_id}.json"
            archive_path.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            entry["message_count"] = len(snapshot.get("messages", []))
            idx.setdefault("archives", {})[agent_id] = str(archive_path)
        idx.setdefault("hidden", {})[agent_id] = entry
        _save_index(idx)
    return entry


def restore_chat(agent_id: str) -> tuple[bool, str, Optional[dict]]:
    """恢复隐藏的对话，返回可选消息快照。"""
    with _lock:
        idx = _load_index()
        hidden = idx.get("hidden", {})
        if agent_id not in hidden:
            return False, "对话未在归档中", None
        del hidden[agent_id]
        idx["hidden"] = hidden
        _save_index(idx)

    snapshot = None
    archive_path = CHAT_ARCHIVES_DIR / f"{agent_id}.json"
    if archive_path.exists():
        try:
            snapshot = json.loads(archive_path.read_text(encoding="utf-8"))
        except Exception:
            snapshot = None
    return True, "已恢复", snapshot


def _sort_by_hidden_at(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: float(r.get("hidden_at") or 0), reverse=True)


def list_hidden() -> list[dict]:
    idx = _load_index()
    return _sort_by_hidden_at(list(idx.get("hidden", {}).values()))


def search_archives(query: str) -> list[dict]:
    """按 agent_id 或名称检索归档。"""
    q = (query or "").strip().lower()
    if not q:
        return list_hidden()
    results = []
    idx = _load_index()
    for agent_id, meta in idx.get("hidden", {}).items():
        label = str(meta.get("label", agent_id)).lower()
        if q in agent_id.lower() or q in label:
            results.append({**meta, "agent_id": agent_id})
            continue
        archive_path = CHAT_ARCHIVES_DIR / f"{agent_id}.json"
        if archive_path.exists():
            try:
                snap = json.loads(archive_path.read_text(encoding="utf-8"))
                for m in snap.get("messages", [])[:50]:
                    text = str(m.get("text", m.get("content", ""))).lower()
                    if q in text:
                        results.append({**meta, "agent_id": agent_id, "match": "message"})
                        break
            except Exception:
                pass
    return _sort_by_hidden_at(results)


def is_hidden(agent_id: str) -> bool:
    return agent_id in _load_index().get("hidden", {})
