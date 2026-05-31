"""Reliable agent-notify launch + skills.log handshake (dispatch / resume).

Agent ACK mechanism:
  After notify_handshake succeeds, dispatch waits for the target Agent
  to write a .ack file confirming it has started processing the task.
  If no ACK within ACK_TIMEOUT_SEC (default 300s / 5 min), the dispatch
  is considered failed and will be retried.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def notify_script_path() -> Path:
    return (
        Path.home()
        / ".openclaw"
        / "skills"
        / "team-ok"
        / "agent-notify"
        / "scripts"
        / "notify_agent.py"
    )


def skills_log_path(project_id: str) -> Path:
    return (
        Path.home()
        / ".openclaw"
        / "tasks"
        / "projects"
        / project_id
        / "skill-logs"
        / "skills.log"
    )


def ack_file_path(agent_id: str, project_id: str, task_id: str) -> Path:
    """Path to the ACK file the Agent writes to confirm it has started processing."""
    return (
        Path.home()
        / ".openclaw"
        / f"workspace-{agent_id}"
        / ".trigger"
        / f"{project_id}_{task_id}.ack"
    )


def trigger_file_path(agent_id: str, project_id: str, task_id: str) -> Path:
    """Path to the trigger file."""
    return (
        Path.home()
        / ".openclaw"
        / f"workspace-{agent_id}"
        / ".trigger"
        / f"{project_id}_{task_id}.trigger"
    )


from common.config import HANDSHAKE_ACK_TIMEOUT


ACK_TIMEOUT_SEC = HANDSHAKE_ACK_TIMEOUT  # 5 min


def wait_for_agent_ack(agent_id: str, project_id: str, task_id: str, logger) -> tuple[bool, str]:
    """Wait for the target Agent to write a .ack file confirming execution start.

    Polls every 5 seconds up to ACK_TIMEOUT_SEC seconds.
    Returns (True, '') on success or (False, error_message) on timeout.
    """
    ack_path = ack_file_path(agent_id, project_id, task_id)
    deadline = time.time() + ACK_TIMEOUT_SEC

    logger.info(
        f"[ACK_WAIT_START] agent={agent_id}, project={project_id}, task={task_id}, "
        f"timeout={ACK_TIMEOUT_SEC}s, ack_file={ack_path}",
        extra={"skill_name": "DISPATCH"},
    )

    while time.time() < deadline:
        if ack_path.exists():
            try:
                ack_data = json.loads(ack_path.read_text(encoding="utf-8"))
                acked_at = ack_data.get("acked_at", "unknown")
                logger.info(
                    f"[ACK_RECEIVED] agent={agent_id}, project={project_id}, "
                    f"task={task_id}, acked_at={acked_at}",
                    extra={"skill_name": "DISPATCH"},
                )
                return True, ""
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(
                    f"[ACK_READ_FAIL] file={ack_path}, error={e}",
                    extra={"skill_name": "DISPATCH"},
                )
                # File exists but unreadable — treat as ack anyway
                return True, ""
        time.sleep(5)

    logger.error(
        f"[ACK_TIMEOUT] agent={agent_id}, project={project_id}, task={task_id}, "
        f"waited={ACK_TIMEOUT_SEC}s",
        extra={"skill_name": "DISPATCH"},
    )
    return False, f"Agent {agent_id} 未在 {ACK_TIMEOUT_SEC}s 内确认执行（无 .ack 文件）"


def cleanup_trigger(agent_id: str, project_id: str, task_id: str) -> None:
    """Remove trigger and ack files for a task."""
    for p in [trigger_file_path(agent_id, project_id, task_id),
              ack_file_path(agent_id, project_id, task_id)]:
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass


def _notify_started_in_log(log_path: Path, task_id: str, since_pos: int) -> bool:
    if not log_path.exists():
        return False
    try:
        text = log_path.read_text(encoding="utf-8")
    except OSError:
        return False
    tail = text[since_pos:] if since_pos <= len(text) else text
    needle_dispatch = f"task={task_id}"
    for line in tail.splitlines():
        if "[NOTIFY_DISPATCH_START]" not in line or needle_dispatch not in line:
            continue
        if "[AGENT_NOTIFY]" in line:
            return True
    return False


def _notify_never_started_logged(log_path: Path, task_id: str, since_pos: int) -> bool:
    if not log_path.exists():
        return False
    try:
        text = log_path.read_text(encoding="utf-8")
    except OSError:
        return False
    tail = text[since_pos:] if since_pos <= len(text) else text
    return any(
        "[AGENT_NOTIFY_NEVER_STARTED]" in line and f"task={task_id}" in line
        for line in tail.splitlines()
    )


def handshake_timeout_sec() -> int:
    try:
        return max(5, int(os.environ.get("DISPATCH_NOTIFY_HANDSHAKE_SEC", "45")))
    except ValueError:
        return 45


OPENCODE_SESSION_MAP_PATH = Path.home() / ".openclaw" / "opencode_session_map.json"


def check_agent_session_active(agent_id: str) -> tuple[bool, str]:
    """Check if the Agent's opencode session is truly active.

    Returns (True, '') if the session exists and has been used,
    or (False, reason) if the session is stuck/never-used/missing.
    """
    if not OPENCODE_SESSION_MAP_PATH.exists():
        return False, "session_map 不存在"

    try:
        sessions = json.loads(OPENCODE_SESSION_MAP_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return False, f"session_map 读取失败: {e}"

    key = f"{agent_id}:{agent_id}:workspace-{agent_id}"
    session = sessions.get(key)
    if not session:
        return False, f"Agent {agent_id} 无活跃会话"

    last_used = session.get("last_used", 0)
    created_at = session.get("created_at", 0)

    # Session created but never used
    if last_used == created_at:
        return False, f"Agent {agent_id} 会话创建但从未使用"

    # Session idle for too long (>10 min)
    now = time.time()
    idle_minutes = (now - last_used) / 60
    if idle_minutes > 10:
        return False, f"Agent {agent_id} 会话已静默 {idle_minutes:.0f} 分钟"

    return True, ""


def notify_mode() -> str:
    """sync | detach (default detach)."""
    mode = os.environ.get("DISPATCH_NOTIFY_MODE", "detach").strip().lower()
    return mode if mode in ("sync", "detach") else "detach"


def run_notify_dispatch(
    project_id: str,
    task_id: str,
    agent_id: str,
    logger,
    *,
    skill_name: str = "DISPATCH",
) -> tuple[bool, str]:
    """
    Start notify_agent.py dispatch and confirm NOTIFY_DISPATCH_START in skills.log.

    Returns (success, error_message).
    """
    log_path = skills_log_path(project_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        since_pos = log_path.stat().st_size if log_path.exists() else 0
    except OSError:
        since_pos = 0

    cmd = [
        sys.executable,
        str(notify_script_path()),
        "dispatch",
        project_id,
        task_id,
        agent_id,
    ]

    mode = notify_mode()
    logger.info(
        f"[AGENT_NOTIFY_START] agent={agent_id}, project={project_id}, task={task_id}, mode={mode}",
        extra={"skill_name": skill_name},
    )

    if mode == "sync":
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=int(os.environ.get("DISPATCH_NOTIFY_SYNC_TIMEOUT", "1800")),
            )
        except subprocess.TimeoutExpired:
            return False, "notify sync timeout"
        if result.returncode != 0:
            return False, (result.stderr or result.stdout or "notify failed")[:500]
        if not _notify_started_in_log(log_path, task_id, since_pos):
            return False, "NOTIFY_DISPATCH_START not found after sync notify"
        logger.info(
            f"[AGENT_NOTIFY_SUCCESS] agent={agent_id}, project={project_id}, task={task_id}, mode=sync",
            extra={"skill_name": skill_name},
        )
        return True, ""

    # detach: child survives parent exit; parent waits for handshake only
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except Exception as e:
        return False, str(e)

    deadline = time.time() + handshake_timeout_sec()
    poll = 0.25
    while time.time() < deadline:
        if _notify_started_in_log(log_path, task_id, since_pos):
            logger.info(
                f"[AGENT_NOTIFY_HANDSHAKE_OK] agent={agent_id}, project={project_id}, task={task_id}",
                extra={"skill_name": skill_name},
            )
            return True, ""
        if proc.poll() is not None and proc.returncode != 0:
            err = ""
            try:
                err = (proc.stderr.read() or b"").decode("utf-8", errors="replace")[:500]
            except Exception:
                err = "[stderr read error]"
            return False, err or f"notify process exited {proc.returncode}"
        time.sleep(poll)

    # Handshake failed — reap child if still running
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    if not _notify_never_started_logged(log_path, task_id, since_pos):
        msg = (
            f"[AGENT_NOTIFY_NEVER_STARTED] agent={agent_id}, project={project_id}, "
            f"task={task_id}, waited_sec={handshake_timeout_sec()}"
        )
        logger.error(msg, extra={"skill_name": skill_name})

    return False, f"notify handshake timeout ({handshake_timeout_sec()}s)"


def release_queue(project_id: str) -> None:
    subprocess.run(
        [
            str(
                Path.home()
                / ".openclaw"
                / "skills"
                / "team-ok"
                / "task-queue"
                / "scripts"
                / "task_queue.py"
            ),
            "release",
            project_id,
        ],
        capture_output=True,
        text=True,
    )
