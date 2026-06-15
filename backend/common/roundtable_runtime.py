#!/usr/bin/env python3
"""圆桌讨论运行时 — 超时、失败可见、transcript 增量落盘。"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable, Optional

logger = logging.getLogger("roundtable_runtime")

DEFAULT_ROUNDTABLE_TURN_TIMEOUT = 300


from common.thinking_trace import append_thinking_sse


@dataclass
class TurnResult:
    ok: bool
    text: str
    error_code: str = ""
    error_message: str = ""
    duration_ms: int = 0
    parts: list | None = None
    partial_text: str = ""

    def __post_init__(self) -> None:
        if self.parts is None:
            self.parts = []


def _append_stream_trace(
    evt: dict,
    reply_parts: list[str],
    trace_parts: list[dict],
) -> None:
    """从 SSE 事件收集最终正文与可持久化的活动轨迹（工具调用等）。"""
    append_thinking_sse(evt, reply_parts, trace_parts, max_parts=MAX_TURN_TRACE_PARTS)


MAX_TURN_TRACE_PARTS = 120


def roundtable_turn_timeout(default: int = DEFAULT_ROUNDTABLE_TURN_TIMEOUT) -> int:
    try:
        from common.skill_settings import roundtable_turn_timeout_sec

        return roundtable_turn_timeout_sec(default)
    except Exception:
        return default


def roundtable_session_timeout_seconds(
    speaker_count: int,
    max_rounds: int,
    *,
    turn_timeout: int | None = None,
) -> int:
    """整桌上限：轮数 × 每轮发言量 × turn 超时 + 缓冲。"""
    tt = turn_timeout or roundtable_turn_timeout()
    # thinking 并行 + opening n + (facilitator + alignment n + draft + confirm n) * rounds
    turns_estimate = speaker_count + max_rounds * (2 * speaker_count + 3) + speaker_count
    return int(turns_estimate * tt * 1.15) + 120


def start_session_deadline_watch(
    cancel_event: Optional[Event],
    deadline_seconds: int,
) -> None:
    """到期后 set cancel_event，避免整桌无限挂起。"""
    if cancel_event is None or deadline_seconds <= 0:
        return

    def _watch() -> None:
        if cancel_event.wait(deadline_seconds):
            return
        if not cancel_event.is_set():
            logger.warning("roundtable session deadline reached (%ss)", deadline_seconds)
            cancel_event.set()

    threading.Thread(target=_watch, daemon=True, name="roundtable-session-deadline").start()


def _classify_error(message: str) -> str:
    msg = (message or "").strip()
    if not msg:
        return "EMPTY_REPLY"
    if msg in ("已取消",) or "cancel" in msg.lower():
        return "CANCELLED"
    if "超时" in msg or "timeout" in msg.lower():
        return "TIMEOUT"
    if "误走任务" in msg or "trigger" in msg.lower():
        return "INVALID_WORKER_REPLY"
    if "未返回" in msg:
        return "EMPTY_REPLY"
    return "STREAM_ERROR"


def classify_turn_error(message: str) -> str:
    return _classify_error(message)


def _merge_turn_cancel(
    user_cancel: Optional[Event],
    turn_timeout: int,
) -> tuple[Event, Event]:
    """返回 (effective_cancel, timeout_flag)。"""
    effective = Event()
    timed_out = Event()

    def _watch() -> None:
        deadline = time.monotonic() + turn_timeout
        while not effective.is_set():
            if user_cancel and user_cancel.is_set():
                effective.set()
                return
            if time.monotonic() >= deadline:
                timed_out.set()
                effective.set()
                return
            time.sleep(0.25)

    threading.Thread(target=_watch, daemon=True, name="roundtable-turn-timeout").start()
    return effective, timed_out


def collect_roundtable_reply(
    agent_id: str,
    prompt: str,
    cancel_event: Optional[Event],
    *,
    group_id: str = "",
    project_id: str = "",
    reply_to_msg_id: str = "",
    max_attempts: int = 2,
    fanout_done: bool = False,
    is_invalid_reply: Optional[Callable[[str], bool]] = None,
    turn_timeout: int | None = None,
) -> TurnResult:
    """收集 stream_chat 回复，带 per-turn 超时与错误码。"""
    try:
        from base.agent_chat import stream_chat
    except ImportError:
        return TurnResult(False, "", "STREAM_ERROR", "stream_chat unavailable")

    fanout_stream_event = None
    try:
        from hub.services.stream_fanout import fanout_stream_event as _fanout

        fanout_stream_event = _fanout
    except ImportError:
        pass

    timeout_sec = turn_timeout or roundtable_turn_timeout()
    invalid = is_invalid_reply or (lambda _t: False)
    started = time.monotonic()
    last_error = ""
    current_prompt = prompt
    last_trace_parts: list[dict] = []
    last_partial_text = ""

    for _attempt in range(max_attempts):
        turn_cancel, timed_out = _merge_turn_cancel(cancel_event, timeout_sec)
        reply_parts: list[str] = []
        trace_parts: list[dict] = []
        error = ""
        try:
            for sse_json in stream_chat(
                agent_id,
                current_prompt,
                cancel_event=turn_cancel,
                rules_profile="discussion",
                group_id=group_id,
                project_id=project_id,
                memory_mode="roundtable",
            ):
                if cancel_event and cancel_event.is_set():
                    msg = "已取消"
                    return TurnResult(
                        False, msg, _classify_error(msg), msg,
                        int((time.monotonic() - started) * 1000),
                        list(trace_parts),
                    )
                if group_id and fanout_stream_event:
                    try:
                        evt_raw = json.loads(sse_json)
                    except json.JSONDecodeError:
                        evt_raw = {}
                    if fanout_done or evt_raw.get("event") != "done":
                        fanout_stream_event(
                            agent_id,
                            sse_json,
                            group_id=group_id,
                            reply_to=reply_to_msg_id,
                        )
                try:
                    evt = json.loads(sse_json)
                except json.JSONDecodeError:
                    continue
                event = evt.get("event")
                if event == "error":
                    error = (evt.get("data") or {}).get("message", "unknown error")
                else:
                    _append_stream_trace(evt, reply_parts, trace_parts)
                if event == "done":
                    summary = (evt.get("data") or {}).get("summary", "") or ""
                    if summary and not reply_parts:
                        reply_parts.append(summary)
                    break
        except Exception as e:
            last_error = str(e)
            last_trace_parts = list(trace_parts)
            last_partial_text = "".join(reply_parts).strip()
            continue

        last_trace_parts = list(trace_parts)
        last_partial_text = "".join(reply_parts).strip()
        duration_ms = int((time.monotonic() - started) * 1000)
        if timed_out.is_set() and not reply_parts:
            last_error = f"Timeout: Agent '{agent_id}' 讨论超时（{timeout_sec}s）"
            last_trace_parts = list(trace_parts)
            last_partial_text = "".join(reply_parts).strip()
            continue
        if error:
            last_error = error
            last_trace_parts = list(trace_parts)
            last_partial_text = "".join(reply_parts).strip()
            continue
        text = "".join(reply_parts).strip()
        if not text:
            last_error = f"Agent '{agent_id}' 未返回讨论内容"
            last_trace_parts = list(trace_parts)
            last_partial_text = ""
            current_prompt = (
                f"{prompt}\n\n---\n"
                "**再次强调**：讨论模式，请输出结构化讨论正文；"
                "若缺事实可用 WebSearch/WebFetch/Read/Grep 调研。"
            )
            continue
        if invalid(text):
            last_error = "回复误走任务通知流程，非讨论内容"
            last_trace_parts = list(trace_parts)
            last_partial_text = text
            current_prompt = (
                f"{prompt}\n\n---\n"
                "你刚才的回复像是在执行 worker 任务流（检查 trigger 等），这是错误的。"
                "当前为讨论模式，请仅基于议题发表专业观点，用 ## 小标题 + 列表。"
            )
            continue
        return TurnResult(
            True, text, "", "",
            duration_ms,
            list(trace_parts),
        )

    msg = last_error or f"Agent '{agent_id}' 未返回有效讨论内容"
    return TurnResult(
        False, msg, _classify_error(msg), msg,
        int((time.monotonic() - started) * 1000),
        list(last_trace_parts),
        partial_text=last_partial_text,
    )


_CHECKPOINT_LEAK_RE = re.compile(
    r"(?:\n|^)Continue if you have next steps.*$",
    re.IGNORECASE | re.DOTALL,
)
_SESSION_STATE_BLOCK_RE = re.compile(
    r"(?:\n|^)## Goal\n.*",
    re.DOTALL,
)
_VOTE_LINE_GLUE_RE = re.compile(
    r"(CONSENSUS_VOTE:\s*(?:AGREE|同意|OBJECT|反对|ABSTAIN|弃权))\s*(?=[#\*])",
    re.IGNORECASE,
)
_GOAL_GLUE_RE = re.compile(r"([^\n])(## Goal\b)", re.IGNORECASE)
_CORRECTION_ITEM_RE = re.compile(
    r"####\s*修正项\s*(\d+)\s*[:：]\s*([^\n]+)\n(.*?)(?=\n####\s*修正项|\n---|\n## [^#]|\Z)",
    re.DOTALL,
)
_ASSESSMENT_SLUG_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)


def sanitize_roundtable_public_text(text: str) -> str:
    """去掉 OpenCode checkpoint / session 结构化块等不应出现在群聊的正文泄漏。"""
    if not text:
        return text
    out = _GOAL_GLUE_RE.sub(r"\1\n\2", text)
    out = _VOTE_LINE_GLUE_RE.sub(r"\1\n", out)
    out = _CHECKPOINT_LEAK_RE.sub("", out)
    out = _SESSION_STATE_BLOCK_RE.sub("", out)
    return out.rstrip()


def extract_correction_items(text: str) -> list[tuple[int, str, str]]:
    """从最佳实践草案提取「修正项 N」块，返回 (序号, 标题, 正文)。"""
    if not text:
        return []
    items: list[tuple[int, str, str]] = []
    for match in _CORRECTION_ITEM_RE.finditer(text):
        num = int(match.group(1))
        title = match.group(2).strip()
        body = match.group(3).strip()
        items.append((num, title, body))
    return sorted(items, key=lambda x: x[0])


def _assessment_slug(agenda: str, *, max_len: int = 48) -> str:
    raw = (agenda or "roundtable").strip().lower()
    slug = _ASSESSMENT_SLUG_RE.sub("-", raw).strip("-")
    if not slug:
        slug = "roundtable"
    return slug[:max_len].strip("-")


def build_best_practice_assessment_markdown(
    *,
    agenda: str,
    group_name: str,
    draft_text: str,
    transcript_rel_path: str,
    msg_id: str,
    generated_at: float | None = None,
) -> str:
    """将圆桌通过的修正项整理为 docs/assessments 落盘正文。"""
    ts = time.strftime(
        "%Y-%m-%d %H:%M:%S",
        time.localtime(generated_at or time.time()),
    )
    corrections = extract_correction_items(draft_text)
    lines = [
        "# 圆桌最佳实践修正项汇总\n",
        "\n",
        f"> **议题**：{agenda.strip() or '（未指定）'}\n",
        f"> **群组**：{group_name.strip() or '（未知）'}\n",
        f"> **状态**：BEST_PRACTICE: PASSED（交叉确认投票通过）\n",
        f"> **圆桌记录**：`{transcript_rel_path}`\n",
        f"> **消息 ID**：`{msg_id}`\n",
        f"> **生成时间**：{ts}\n",
        "\n",
        "## 总判定\n",
        "\n",
        "Workflow v3 骨架正确（P1→P2→P3→P4 + P3 内并行扇出），经下列修正项后可执行。\n",
        "\n",
    ]
    if not corrections:
        lines.extend([
            "## 修正项\n",
            "\n",
            "_草案中未解析到「修正项 N」结构化条目；请查看圆桌记录全文。_\n",
            "\n",
        ])
    else:
        lines.append(f"## 修正项（共 {len(corrections)} 项）\n\n")
        for num, title, body in corrections:
            lines.append(f"### 修正项 {num}：{title}\n\n")
            lines.append(f"{body}\n\n")
    lines.append("## 来源\n\n")
    lines.append(
        "由群组圆桌 `_run_group_roundtable` 在共识确认通过后自动整理；"
        "内容摘自主持人最佳实践草案中的「修正项」章节。\n",
    )
    return "".join(lines)


def write_best_practice_assessment(
    *,
    agenda: str,
    group_name: str,
    draft_text: str,
    transcript_rel_path: str,
    msg_id: str,
) -> Path | None:
    """共识通过后写入 docs/assessments/；无修正项时仍落盘摘要。"""
    from common.paths import MYTEAM_ROOT, to_relative_path

    corrections = extract_correction_items(draft_text)
    if not draft_text.strip():
        return None

    assessments_dir = MYTEAM_ROOT / "docs" / "assessments"
    assessments_dir.mkdir(parents=True, exist_ok=True)
    suffix = msg_id.replace("m_", "")[:16] if msg_id else str(int(time.time()))
    slug = _assessment_slug(agenda)
    path = assessments_dir / f"roundtable-{slug}-{suffix}.md"
    if path.exists():
        path = assessments_dir / f"roundtable-{slug}-{suffix}-{int(time.time())}.md"

    body = build_best_practice_assessment_markdown(
        agenda=agenda,
        group_name=group_name,
        draft_text=draft_text,
        transcript_rel_path=transcript_rel_path,
        msg_id=msg_id,
    )
    path.write_text(body, encoding="utf-8")
    logger.info(
        "roundtable assessment written: %s (%d corrections)",
        to_relative_path(path),
        len(corrections),
    )
    return path


def flush_roundtable_transcript(path: Path, lines: list[str]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(lines), encoding="utf-8")
    except OSError as e:
        logger.warning("flush roundtable transcript failed: %s", e)


def append_turn_failure_message(
    append_message: Callable[..., None],
    *,
    group_id: str,
    msg_id: str,
    agent_id: str,
    phase: str,
    round_num: int,
    error_code: str,
    detail: str,
    project_id: str = "",
) -> dict:
    """写入群可见的失败记录（system 消息）。"""
    entry = {
        "id": f"m_{int(time.time() * 1000000)}_{agent_id}_fail",
        "sender": "system",
        "text": (
            f"圆桌发言失败：@{agent_id} · {phase} · {error_code}\n"
            f"{detail}"
        ),
        "timestamp": time.time(),
        "mentions": [agent_id],
        "in_reply_to": msg_id,
        "roundtable": True,
        "roundtable_phase": "turn_failed",
        "roundtable_round": round_num,
        "roundtable_meta": {
            "agent_id": agent_id,
            "intended_phase": phase,
            "error_code": error_code,
            "detail": detail,
        },
    }
    append_message(group_id, entry, project_id=project_id)
    return entry


def format_failure_transcript_line(
    *,
    label: str,
    agent_id: str,
    agent_name: str,
    error_code: str,
    detail: str,
) -> str:
    return (
        f"\n\n---\n\n## [{label}] {agent_name} (@{agent_id})\n\n"
        f"**失败** `{error_code}`：{detail}\n"
    )
