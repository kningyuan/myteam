"""回归脚本 agents_config 补丁：全文件备份 + finally/atexit 恢复，避免 kill 后残留。"""
from __future__ import annotations

import atexit
import json
import signal
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
CFG_PATH = _REPO / "business/config/agents_config.json"

_backup: str | None = None
_registered = False


def _restore_full() -> None:
    global _backup
    if _backup is None or not CFG_PATH.parent.is_dir():
        return
    CFG_PATH.write_text(_backup, encoding="utf-8")
    _backup = None


def _register_hooks() -> None:
    global _registered
    if _registered:
        return
    _registered = True
    atexit.register(_restore_full)

    def _on_signal(signum, frame):  # noqa: ARG001
        _restore_full()
        raise SystemExit(128 + signum)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _on_signal)
        except (ValueError, OSError):
            pass


def begin_session() -> None:
    """在首次 patch 前调用：快照整个 agents_config.json。"""
    global _backup
    _register_hooks()
    if _backup is not None:
        return
    if CFG_PATH.is_file():
        _backup = CFG_PATH.read_text(encoding="utf-8")
    else:
        _backup = "{}\n"


def end_session() -> None:
    """恢复 begin_session 时的全文件快照。"""
    _restore_full()


def patch_agent(agent_id: str, **fields: Any) -> dict | None:
    """写入字段；返回该 agent 补丁前的条目（不存在则为 None）。"""
    begin_session()
    if not CFG_PATH.is_file():
        CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
        data: dict = {}
    else:
        data = json.loads(CFG_PATH.read_text(encoding="utf-8"))
    old = data.get(agent_id)
    entry = dict(data.get(agent_id) or {})
    for key, val in fields.items():
        if val is not None:
            entry[key] = val
    entry.setdefault("workspace", f"business/workspaces/workspace-{agent_id}")
    data[agent_id] = entry
    CFG_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    return old if isinstance(old, dict) else None


def patch_agent_claude(agent_id: str, *, model: str) -> dict | None:
    return patch_agent(agent_id, backend="claude", model=model)


class AgentsConfigSession:
    """with 块结束时整文件恢复，比逐 agent restore 更抗中断。"""

    def __enter__(self) -> AgentsConfigSession:
        begin_session()
        return self

    def patch_claude(self, agent_id: str, *, model: str) -> None:
        patch_agent_claude(agent_id, model=model)

    def patch_backend(self, agent_id: str, backend: str) -> None:
        patch_agent(agent_id, backend=backend)

    def __exit__(self, exc_type, exc, tb) -> None:
        end_session()
