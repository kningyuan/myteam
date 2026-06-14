#!/usr/bin/env python3
"""Loop 单轮结束调度 — Kernel 入口，按 workflow profile 委托 business hook。"""
from __future__ import annotations

import logging

from common.business_hook_loader import load_business_hook
from common.loop_discussion_runtime import (
    LoopDiscussionProfile,
    find_project_group,
    group_enabled,
    load_loop_discussion_profile,
    publish_group_message,
    read_deliverable,
    extract_section,
    workflow_discussion_profile_id,
    workflow_group_discussion_enabled,
)

logger = logging.getLogger("loop_discussion_dispatch")


def _review_excerpt(review_text: str, profile: LoopDiscussionProfile) -> tuple[str, str, str]:
    secs = profile.review_sections
    conclusion = extract_section(review_text, secs.get("conclusion", "")) or "（见评审交付物）"
    findings = extract_section(review_text, secs.get("findings", "")) or "—"
    revisions = extract_section(review_text, secs.get("revisions", "")) or "—"
    return conclusion, findings, revisions


def dispatch_loop_round_done(
    project_id: str,
    loop_id: str,
    round_num: int,
    *,
    passed: bool,
    work_task_id: str,
    review_task_id: str,
    max_rounds: int = 5,
    profile: LoopDiscussionProfile | None = None,
) -> None:
    """loop 单轮结束后：通报；FAIL 且启用群讨论时加载 business hook 对齐。"""
    if not group_enabled(project_id):
        return
    group = find_project_group(project_id)
    if not group:
        logger.debug("no project group for %s", project_id)
        return

    if profile is None:
        pid = workflow_discussion_profile_id(project_id)
        profile = load_loop_discussion_profile(pid) if pid else None

    review_agent = (profile.review_agent if profile else "") or "main"
    label = (profile.round_summary_label if profile else "") or "评审"

    review_text = read_deliverable(project_id, review_task_id)
    if profile:
        conclusion, findings, revisions = _review_excerpt(review_text, profile)
    else:
        conclusion, findings, revisions = "（见评审交付物）", "—", "—"

    header = f"📋 第 {round_num}/{max_rounds} 轮 · {label}（{loop_id}）"
    body = (
        f"{header}\n"
        f"work: `{work_task_id}`\n"
        f"review: `{review_task_id}`\n\n"
        f"**审计结论**：{conclusion[:400]}\n\n"
        f"**发现与分级**：\n{findings[:800]}\n\n"
        f"**修订要求**：\n{revisions[:800]}"
    )
    publish_group_message(group["id"], review_agent, body, route_mentions=False)

    pass_marker = profile.pass_marker if profile else "REVIEW: PASS"
    if passed:
        publish_group_message(
            group["id"],
            review_agent,
            f"✅ 第 {round_num} 轮评审通过（{pass_marker}），Work–Review 循环结束。",
            route_mentions=False,
        )
        return

    if round_num >= max_rounds:
        publish_group_message(
            group["id"],
            review_agent,
            f"⚠️ 已达最大 {max_rounds} 轮仍未通过，请在本群或 Hub 人工介入。",
            route_mentions=False,
        )
        return

    if not workflow_group_discussion_enabled(project_id):
        publish_group_message(
            group["id"],
            review_agent,
            (
                f"第 {round_num} 轮评审未通过。"
                f"请阅读 `{review_task_id}_deliverable.md` 修订要求；"
                f"内核将直接启动第 {round_num + 1} 轮改稿（群讨论未启用）。"
            ),
            route_mentions=False,
        )
        return

    if not profile:
        logger.warning("group_discussion enabled but no loop_discussion_profile for %s", project_id)
        publish_group_message(
            group["id"],
            review_agent,
            f"⚠️ 未配置 loop_discussion_profile，跳过群讨论，直接启动第 {round_num + 1} 轮改稿。",
            route_mentions=False,
        )
        return

    hook = load_business_hook(profile.hook_module)
    if hook is None or not hasattr(hook, "run_structured_group_discussion"):
        logger.warning("business hook missing: %s", profile.hook_module)
        return

    ok, err = hook.run_structured_group_discussion(
        project_id,
        group["id"],
        loop_id,
        round_num,
        review_task_id=review_task_id,
        work_task_id=work_task_id,
        findings=findings,
        revisions=revisions,
        profile=profile,
    )
    if not ok:
        logger.warning("group discussion failed for %s r%s: %s", project_id, round_num, err)
        publish_group_message(
            group["id"],
            review_agent,
            f"⚠️ 群讨论对齐失败（{str(err)[:200]}），仍将启动第 {round_num + 1} 轮定点 PATCH，请人工关注。",
            route_mentions=False,
        )
