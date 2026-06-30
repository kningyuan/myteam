#!/usr/bin/env python3
"""Loop 讨论运行时 — Kernel 通用原语（无领域 agent/节名）。"""
from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Any, Optional

import yaml

from common.paths import BUSINESS_DIR, PROJECTS_DIR

logger = logging.getLogger("loop_discussion_runtime")


@dataclass
class LoopDiscussionProfile:
    id: str
    hook_module: str = ""
    work_agent: str = ""
    review_agent: str = ""
    round_summary_label: str = "评审"
    max_alignment_turns: int = 3
    review_sections: dict[str, str] = field(default_factory=dict)
    patch_list_headings: list[str] = field(default_factory=list)
    pass_marker: str = "REVIEW: PASS"
    fail_marker: str = "REVIEW: FAIL"


def load_loop_discussion_profile(profile_id: str) -> Optional[LoopDiscussionProfile]:
    pid = (profile_id or "").strip()
    if not pid:
        return None
    path = BUSINESS_DIR / "workflows" / "profiles" / f"{pid}.yaml"
    if not path.is_file():
        logger.warning("loop discussion profile not found: %s", path)
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return LoopDiscussionProfile(
        id=str(raw.get("id") or pid),
        hook_module=str(raw.get("hook_module") or pid.replace("-", "_")),
        work_agent=str(raw.get("work_agent") or ""),
        review_agent=str(raw.get("review_agent") or ""),
        round_summary_label=str(raw.get("round_summary_label") or "评审"),
        max_alignment_turns=int(raw.get("max_alignment_turns") or 3),
        review_sections=dict(raw.get("review_sections") or {}),
        patch_list_headings=list(raw.get("patch_list_headings") or []),
        pass_marker=str(raw.get("pass_marker") or "REVIEW: PASS"),
        fail_marker=str(raw.get("fail_marker") or "REVIEW: FAIL"),
    )


def read_deliverable(project_id: str, task_id: str) -> str:
    for name in (f"{task_id}_deliverable.md", f"{task_id}.md"):
        fp = PROJECTS_DIR / project_id / "deliverables" / name
        if fp.is_file():
            try:
                return fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return ""
    return ""


def extract_section(text: str, heading: str) -> str:
    if not heading:
        return ""
    pat = re.compile(
        rf"^#{{1,3}}\s+{re.escape(heading)}\s*\n(.*?)(?=^#{{1,3}}\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pat.search(text)
    return m.group(1).strip() if m else ""


def extract_patch_list(text: str, headings: list[str]) -> str:
    for heading in headings:
        block = extract_section(text, heading)
        if block:
            return block
    if not headings:
        return ""
    first = headings[0]
    m = re.search(
        rf"(?:^|\n)(#{{1,3}}\s*{re.escape(first)}.*?)(?=^#{{1,3}}\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return m.group(1).strip() if m else ""


def group_enabled(project_id: str = "") -> bool:
    try:
        from common.workflow.workflow_collaboration import project_group_enabled

        return project_group_enabled(project_id or None)
    except Exception:
        try:
            from common.skill.skill_settings import is_auto_group_enabled

            return is_auto_group_enabled()
        except Exception:
            return True


def find_project_group(project_id: str):
    try:
        from base.group_manager import find_group_by_project

        return find_group_by_project(project_id)
    except Exception as e:
        logger.debug("find_group_by_project: %s", e)
        return None


def publish_group_message(group_id: str, sender: str, text: str, *, route_mentions: bool) -> None:
    try:
        from base.group_manager import send_group_message
        from hub.services.group_broadcast import publish
    except ImportError:
        try:
            from base.group_manager import send_group_message

            for _ in send_group_message(
                group_id, sender, text, route_mentions=route_mentions, route_only=False,
            ):
                pass
        except Exception as e:
            logger.warning("group message failed: %s", e)
        return
    try:
        for evt in send_group_message(
            group_id, sender, text, route_mentions=route_mentions, route_only=False,
        ):
            publish(group_id, evt)
    except Exception as e:
        logger.warning("group message failed: %s", e)


def agent_timeout() -> int:
    try:
        from common.skill.skill_settings import agent_msg_timeout

        return int(agent_msg_timeout())
    except Exception:
        return 300


def collect_agent_reply(agent_id: str, prompt: str, *, group_id: str = "") -> tuple[bool, str]:
    try:
        from base.agent_chat import stream_chat
    except ImportError:
        return False, "stream_chat unavailable"

    fanout = None
    try:
        from hub.services.stream_fanout import fanout_stream_event

        fanout = fanout_stream_event
    except ImportError:
        pass

    cancel = Event()
    threading.Thread(target=lambda: cancel.wait(agent_timeout()), daemon=True).start()

    parts: list[str] = []
    error = ""
    try:
        for sse_json in stream_chat(agent_id, prompt, cancel_event=cancel):
            if cancel.is_set() and not parts:
                return False, f"Timeout: Agent '{agent_id}' 讨论超时"
            if fanout and group_id:
                fanout(agent_id, sse_json, group_id=group_id)
            try:
                evt = json.loads(sse_json)
            except json.JSONDecodeError:
                continue
            event = evt.get("event")
            if event == "error":
                error = (evt.get("data") or {}).get("message", "unknown error")
            elif event == "thinking":
                data = evt.get("data") or {}
                if data.get("type") == "text":
                    text = data.get("content", "")
                    if text:
                        parts.append(text)
            elif event == "text":
                content = (evt.get("data") or {}).get("content", "")
                if content:
                    parts.append(content)
            elif event == "done":
                summary = (evt.get("data") or {}).get("summary", "") or ""
                if summary:
                    parts.append(summary)
                break
    except Exception as e:
        return False, str(e)

    if error:
        return False, error
    text = "".join(parts).strip()
    if not text:
        return False, f"Agent '{agent_id}' 未返回讨论内容"
    return True, text


def discussion_transcript_path(project_id: str, loop_id: str, round_num: int) -> Path:
    return PROJECTS_DIR / project_id / "deliverables" / f"{loop_id}-r{round_num}-group_discussion.md"


def save_discussion_artifacts(
    project_id: str,
    loop_id: str,
    round_num: int,
    *,
    transcript: str,
    summary: str,
    patch_list: str = "",
) -> None:
    fp = discussion_transcript_path(project_id, loop_id, round_num)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(transcript, encoding="utf-8")
    try:
        from common.store.store import Store

        store = Store()
        try:
            meta_kw: dict[str, Any] = {
                "last_loop_discussion": summary,
                "last_loop_discussion_round": round_num,
                "last_loop_discussion_file": str(fp.name),
            }
            if patch_list:
                meta_kw["last_loop_patch_list"] = patch_list
            store.update_project_meta(project_id, **meta_kw)
        finally:
            store.close()
    except Exception as e:
        logger.warning("save discussion meta failed: %s", e)


def workflow_group_discussion_enabled(project_id: str) -> bool:
    try:
        from common.workflow.workflow_collaboration import group_discussion_enabled

        return group_discussion_enabled(project_id)
    except Exception as e:
        logger.debug("workflow group_discussion flag: %s", e)
        return False


def workflow_discussion_profile_id(project_id: str) -> str:
    try:
        from common.workflow.workflow_collaboration import loop_discussion_profile_id

        return loop_discussion_profile_id(project_id)
    except Exception:
        return ""


def setup_project_group_if_needed(project_id: str, agents: list[str], title: str = "") -> None:
    if not group_enabled(project_id):
        return
    try:
        from hub.services.project_group_service import setup_project_group

        setup_project_group(project_id, agents, project_name=title)
    except Exception as e:
        logger.debug("setup_project_group skipped: %s", e)
