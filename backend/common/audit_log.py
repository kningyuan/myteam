#!/usr/bin/env python3
"""协作审计日志开关（D17）—— 开启后把 prompt / 请求 / 响应快照写入 run_event。"""
from __future__ import annotations

import json
from typing import Any


def audit_enabled() -> bool:
    try:
        from store.system_config import system_config
        return bool(system_config.get("system", "audit_log", default=False))
    except Exception:
        return False


def audit_max_bytes() -> int:
    try:
        from store.system_config import system_config
        return int(system_config.get("system", "audit_log_max_bytes", default=500_000))
    except (TypeError, ValueError):
        return 500_000


def clip_text(text: str, max_bytes: int | None = None) -> str:
    max_bytes = max_bytes if max_bytes is not None else audit_max_bytes()
    raw = (text or "").encode("utf-8")
    if len(raw) <= max_bytes:
        return text or ""
    head = raw[:max_bytes].decode("utf-8", errors="ignore")
    return f"{head}\n…[截断，共 {len(raw)} bytes]"


def clip_json(obj: Any, max_bytes: int | None = None) -> Any:
    max_bytes = max_bytes if max_bytes is not None else audit_max_bytes()
    try:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError):
        return {"_error": "不可序列化"}
    if len(raw) <= max_bytes:
        return obj
    return {
        "_truncated": True,
        "_bytes": len(raw),
        "_preview": clip_text(raw.decode("utf-8", errors="ignore"), max_bytes),
    }
