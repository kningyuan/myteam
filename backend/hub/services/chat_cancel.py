"""活跃对话流取消注册表 — 客户端 abort 或显式 /cancel 时终止底层 CLI。"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
import time
from typing import Callable, Generator, TypeVar

logger = logging.getLogger("chat_cancel")

T = TypeVar("T")


class CombinedCancel:
    """合并多个 cancel 源（SSE 断开 + 显式 cancel API）。"""

    __slots__ = ("_events",)

    def __init__(self, *events: threading.Event) -> None:
        self._events = events

    def is_set(self) -> bool:
        return any(e.is_set() for e in self._events)

    def set(self) -> None:
        for e in self._events:
            e.set()


class ChatCancelRegistry:
    _lock = threading.Lock()
    _sessions: dict[str, threading.Event] = {}

    def register(self, session_key: str) -> threading.Event:
        ev = threading.Event()
        with self._lock:
            prev = self._sessions.get(session_key)
            if prev is not None:
                prev.set()
            self._sessions[session_key] = ev
        return ev

    def unregister(self, session_key: str, ev: threading.Event) -> None:
        with self._lock:
            if self._sessions.get(session_key) is ev:
                del self._sessions[session_key]

    def cancel(self, session_key: str) -> bool:
        with self._lock:
            ev = self._sessions.get(session_key)
        if ev is None:
            return False
        ev.set()
        return True


_registry = ChatCancelRegistry()


def register_chat(session_key: str) -> threading.Event:
    return _registry.register(session_key)


def unregister_chat(session_key: str, ev: threading.Event) -> None:
    _registry.unregister(session_key, ev)


def cancel_chat(session_key: str) -> bool:
    return _registry.cancel(session_key)


def is_chat_active(session_key: str) -> bool:
    with _registry._lock:
        return session_key in _registry._sessions


def agent_session_key(agent_id: str) -> str:
    return f"chat:agent:{agent_id}"


def group_session_key(group_id: str) -> str:
    return f"chat:group:{group_id}"


def kill_group_cli_processes(agent_ids: list[str]) -> list[int]:
    """终止群成员 workspace 下可能挂起的 opencode/claude 子进程。"""
    killed: list[int] = []
    seen: set[int] = set()
    for agent_id in agent_ids:
        aid = str(agent_id or "").strip()
        if not aid or aid == "user":
            continue
        patterns = (
            f"workspace-{aid}",
            f"workspaces/{aid}",
        )
        for pattern in patterns:
            try:
                proc = subprocess.run(
                    ["pgrep", "-f", pattern],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            except Exception as exc:
                logger.debug("pgrep failed for %s: %s", pattern, exc)
                continue
            for line in (proc.stdout or "").splitlines():
                line = line.strip()
                if not line.isdigit():
                    continue
                pid = int(line)
                if pid in seen:
                    continue
                seen.add(pid)
                try:
                    os.kill(pid, signal.SIGTERM)
                    killed.append(pid)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    logger.warning("no permission to kill pid %s", pid)
    if killed:
        time.sleep(0.5)
    return killed


def cancel_group_roundtable(
    group_id: str,
    member_ids: list[str] | None = None,
) -> dict:
    """取消群会话并可选终止成员 CLI 进程。"""
    key = group_session_key(group_id)
    cancelled = cancel_chat(key)
    killed: list[int] = []
    try:
        from common.skill_settings import group_discussion_kill_cli_on_cancel

        if group_discussion_kill_cli_on_cancel() and member_ids:
            killed = kill_group_cli_processes(member_ids)
    except Exception as exc:
        logger.debug("kill_cli_on_cancel skipped: %s", exc)
    return {
        "cancelled": cancelled,
        "killed_pids": killed,
        "active": cancelled or bool(killed),
    }


def wrap_producer(
    session_key: str,
    inner: Callable[[CombinedCancel], Generator[T, None, None]],
) -> Callable[[threading.Event], Generator[T, None, None]]:
    """将 SSE 断开 cancel 与显式 /cancel API 合并为单一 cancel 源。"""

    def produce(disconnect_cancel: threading.Event) -> Generator[T, None, None]:
        reg_ev = register_chat(session_key)
        combined = CombinedCancel(disconnect_cancel, reg_ev)
        try:
            yield from inner(combined)
        finally:
            unregister_chat(session_key, reg_ev)

    return produce
