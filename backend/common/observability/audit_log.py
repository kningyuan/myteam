#!/usr/bin/env python3
"""协作审计日志开关（D17）—— 开启后把 prompt / 请求 / 响应快照写入 run_event。"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def audit_enabled() -> bool:
    try:
        from config_store.system_config import system_config
        return bool(system_config.get("system", "audit_log", default=False))
    except Exception:
        return False


def audit_max_bytes() -> int:
    try:
        from config_store.system_config import system_config
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


def stable_json(obj: Any) -> str:
    """生成稳定 JSON 文本，供审计 hash 使用。"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def hash_json(obj: Any) -> str:
    """对 JSON 兼容对象计算 sha256。"""
    return hashlib.sha256(stable_json(obj).encode("utf-8")).hexdigest()


def audit_snapshot(content_key: str, content: Any, **meta: Any) -> dict:
    """构造可校验的审计快照 payload。

    `content_hash` 覆盖原始 request/response；`audit_hash` 覆盖可见 payload，
    因此篡改任一字段都会被 `verify_audit_snapshot` 发现。
    """
    payload = dict(meta)
    payload[content_key] = clip_json(content)
    payload[f"{content_key}_hash"] = hash_json(content)
    payload["audit_hash"] = hash_json(payload)
    return payload


def verify_audit_snapshot(payload: dict, content_key: str) -> bool:
    """校验审计快照是否被篡改。"""
    if not isinstance(payload, dict):
        return False
    expected_hash = payload.get(f"{content_key}_hash")
    visible = payload.get(content_key)
    if (
        content_key in payload
        and not (isinstance(visible, dict) and visible.get("_truncated") is True)
        and expected_hash != hash_json(visible)
    ):
        return False
    audit_hash = payload.get("audit_hash")
    if not isinstance(audit_hash, str):
        return False
    body = {k: v for k, v in payload.items() if k != "audit_hash"}
    return audit_hash == hash_json(body)
