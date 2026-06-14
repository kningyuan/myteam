#!/usr/bin/env python3
"""向后兼容 shim — 实现已迁至 loop_discussion_runtime / loop_discussion_dispatch / business/hooks。"""
from __future__ import annotations

from common.business_hook_loader import load_business_hook
from common.loop_discussion_dispatch import dispatch_loop_round_done as facilitate_loop_round_discussion
from common.loop_discussion_runtime import (
    LoopDiscussionProfile,
    extract_section as _extract_section,
    load_loop_discussion_profile,
    read_deliverable as _read_deliverable,
    setup_project_group_if_needed,
)


def run_structured_group_discussion(
    project_id: str,
    group_id: str,
    loop_id: str,
    round_num: int,
    *,
    review_task_id: str,
    work_task_id: str,
    findings: str,
    revisions: str,
    profile: LoopDiscussionProfile | None = None,
    work_agent: str = "",
    review_agent: str = "",
    **kwargs,
):
    hook = load_business_hook("work_review_alignment")
    if hook is None:
        raise RuntimeError("business hook work_review_alignment not found")
    prof = profile or load_loop_discussion_profile("work-review-alignment")
    if prof is None:
        raise RuntimeError("profile work-review-alignment not found")
    if work_agent:
        prof.work_agent = work_agent
    if review_agent:
        prof.review_agent = review_agent
    return hook.run_structured_group_discussion(
        project_id, group_id, loop_id, round_num,
        review_task_id=review_task_id,
        work_task_id=work_task_id,
        findings=findings,
        revisions=revisions,
        profile=prof,
    )


__all__ = [
    "facilitate_loop_round_discussion",
    "run_structured_group_discussion",
    "setup_project_group_if_needed",
    "_extract_section",
    "_read_deliverable",
]
