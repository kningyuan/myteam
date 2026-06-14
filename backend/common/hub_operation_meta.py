#!/usr/bin/env python3
"""Hub 内显式操作时间 — 仅在 Hub 创建/编辑/删除时更新，不用文件 mtime 或运行时访问。"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from common.paths import BUSINESS_CONFIG_DIR

_META_FILE = BUSINESS_CONFIG_DIR / "hub_operation_meta.json"
_LOCK = threading.Lock()

VALID_KINDS = frozenset({
    "agent",
    "task_type",
    "workflow",
    "delivery_template",
})


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _touch_sort_key(raw: Any) -> float:
    """从 touch 存贮值提取可排序键（越大越新）。"""
    if isinstance(raw, dict):
        ns = raw.get("ns")
        if ns is not None:
            try:
                return float(ns) / 1e9
            except (TypeError, ValueError):
                pass
        raw = raw.get("ts") or ""
    ts = str(raw or "")
    if not ts:
        return 0.0
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _touch_display_ts(raw: Any) -> Optional[str]:
    if isinstance(raw, dict):
        t = raw.get("ts")
        return str(t) if t else None
    return str(raw) if raw else None


def _load_raw() -> dict[str, Any]:
    if not _META_FILE.is_file():
        return {}
    try:
        data = json.loads(_META_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_raw(data: dict[str, Any]) -> None:
    _META_FILE.parent.mkdir(parents=True, exist_ok=True)
    _META_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def touch(kind: str, entity_id: str) -> str:
    """记录 Hub 内一次创建/编辑/删除操作，返回 ISO 时间戳。"""
    k = (kind or "").strip()
    eid = (entity_id or "").strip()
    if k not in VALID_KINDS:
        raise ValueError(f"未知 hub operation kind: {k}")
    if not eid:
        raise ValueError("entity_id 不能为空")
    ts = _utc_now_iso()
    ns = time.time_ns()
    with _LOCK:
        data = _load_raw()
        bucket = data.setdefault(k, {})
        if not isinstance(bucket, dict):
            bucket = {}
            data[k] = bucket
        bucket[eid] = {"ts": ts, "ns": ns}
        _save_raw(data)
    return ts


def remove(kind: str, entity_id: str) -> None:
    k = (kind or "").strip()
    eid = (entity_id or "").strip()
    if k not in VALID_KINDS or not eid:
        return
    with _LOCK:
        data = _load_raw()
        bucket = data.get(k)
        if not isinstance(bucket, dict) or eid not in bucket:
            return
        del bucket[eid]
        _save_raw(data)


def rename(kind: str, old_id: str, new_id: str) -> None:
    old_id = (old_id or "").strip()
    new_id = (new_id or "").strip()
    if not old_id or not new_id or old_id == new_id:
        return
    with _LOCK:
        data = _load_raw()
        bucket = data.get(kind)
        if not isinstance(bucket, dict):
            return
        prev = bucket.pop(old_id, None)
        bucket[new_id] = _utc_now_iso() if prev is None else prev
        _save_raw(data)


def get_ts(kind: str, entity_id: str) -> Optional[str]:
    bucket = _load_raw().get(kind) or {}
    if not isinstance(bucket, dict):
        return None
    raw = bucket.get((entity_id or "").strip())
    return _touch_display_ts(raw)


def map_for_kind(kind: str) -> dict[str, str]:
    bucket = _load_raw().get(kind) or {}
    if not isinstance(bucket, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in bucket.items():
        if k.startswith("_"):
            continue
        ts = _touch_display_ts(v)
        if ts:
            out[str(k)] = ts
    return out


def attach_operated_at(
    items: list[dict[str, Any]],
    kind: str,
    *,
    id_key: str = "id",
    alt_id_key: Optional[str] = None,
) -> list[dict[str, Any]]:
    """为列表项附加 operated_at（Hub 操作时间，无则为空字符串）。"""
    ts_map = map_for_kind(kind)
    out: list[dict[str, Any]] = []
    for item in items:
        row = dict(item)
        eid = str(row.get(id_key) or (row.get(alt_id_key or "") if alt_id_key else "") or "")
        row["operated_at"] = ts_map.get(eid, "")
        out.append(row)
    return out


def sort_by_operated_at(
    items: list[dict[str, Any]],
    *,
    id_key: str = "id",
    alt_id_key: Optional[str] = None,
) -> list[dict[str, Any]]:
    """最近 Hub 操作在前；无 operated_at 的排最后，同组内按 id。"""

    def sort_key(row: dict[str, Any]) -> tuple[float, str]:
        ts = row.get("operated_at") or ""
        rank = _touch_sort_key(ts) if ts else 0.0
        eid = str(row.get(id_key) or (row.get(alt_id_key or "") if alt_id_key else "") or "")
        return (rank, eid)

    return sorted(items, key=sort_key, reverse=True)
