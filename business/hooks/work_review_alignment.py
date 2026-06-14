#!/usr/bin/env python3
"""Business hook — Work–Review FAIL 后 product↔main 定点对齐（领域 prompts）。"""
from __future__ import annotations

import re

from common.loop_discussion_runtime import (
    LoopDiscussionProfile,
    collect_agent_reply,
    extract_patch_list,
    publish_group_message,
    save_discussion_artifacts,
)

_ALIGN_OK_RE = re.compile(
    r"ALIGN:\s*OK|已达成一致|可以照此(?:改|修补)|按此(?:改|修补)", re.IGNORECASE,
)
_ALIGN_NEED_RE = re.compile(r"ALIGN:\s*NEED_MORE|仍需调整|尚不一致", re.IGNORECASE)


def _main_aligned(main_reply: str) -> bool:
    if _ALIGN_OK_RE.search(main_reply):
        return True
    return bool(_ALIGN_NEED_RE.search(main_reply)) is False and "达成一致" in main_reply


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
    profile: LoopDiscussionProfile,
) -> tuple[bool, str]:
    work_agent = profile.work_agent
    review_agent = profile.review_agent
    max_turns = profile.max_alignment_turns

    publish_group_message(
        group_id,
        review_agent,
        (
            f"💬 第 {round_num} 轮评审未通过。"
            f"请在群内与 @{work_agent} **定点对齐**改稿范围（不重做方案），一致后再 PATCH。"
        ),
        route_mentions=False,
    )

    transcript_parts: list[str] = [f"# 第 {round_num} 轮群讨论对齐（{loop_id}）\n"]
    ctx = (
        f"**发现与分级**\n{findings[:1200]}\n\n"
        f"**修订要求**\n{revisions[:1200]}\n\n"
        f"**当前 work 交付物**：`{work_task_id}_deliverable.md`"
    )
    work_reply = ""
    review_reply = ""
    patch_list = ""
    aligned = False

    for turn in range(1, max_turns + 1):
        if turn == 1:
            work_prompt = (
                f"[项目群讨论 · 第 {round_num} 轮 · 定点对齐 · turn {turn}]\n"
                f"你是 @{work_agent}。评审 FAIL（`{review_task_id}`）。\n"
                f"**不要重写整章**。请列出需修改的 ### 小节（仅阻塞项 🔴 + 必要 🟡），"
                f"每条说明「原文问题 → 拟改法」。末尾加 `## 定点改稿清单` 表格或列表。\n"
                f"不要 @ 其他 Agent，不要 JSON。\n\n{ctx}"
            )
        else:
            work_prompt = (
                f"[项目群讨论 · 第 {round_num} 轮 · 补充对齐 · turn {turn}]\n"
                f"你是 @{work_agent}。@{review_agent} 认为尚未完全一致：\n\n---\n{review_reply}\n---\n\n"
                f"逐条回应并更新 `## 定点改稿清单`（仅保留仍需修改的条目）。\n"
                f"不要 @ 其他 Agent，不要 JSON。"
            )

        ok, work_reply = collect_agent_reply(work_agent, work_prompt, group_id=group_id)
        if not ok:
            return False, work_reply
        publish_group_message(group_id, work_agent, work_reply, route_mentions=False)
        transcript_parts.append(f"## turn {turn} · @{work_agent}\n\n{work_reply}\n")

        review_prompt = (
            f"[项目群讨论 · 第 {round_num} 轮 · 评审确认 · turn {turn}]\n"
            f"你是 @{review_agent}（评审）。@{work_agent} 提议定点 PATCH：\n\n---\n{work_reply}\n---\n\n"
            f"逐条确认：可照此改 / 仍需调整。若全部可执行，末行写 `ALIGN: OK`；"
            f"若还有分歧，末行写 `ALIGN: NEED_MORE` 并说明。\n"
            f"不要 @ 其他 Agent，不要 JSON。"
        )
        ok, review_reply = collect_agent_reply(review_agent, review_prompt, group_id=group_id)
        if not ok:
            return False, review_reply
        publish_group_message(group_id, review_agent, review_reply, route_mentions=False)
        transcript_parts.append(f"## turn {turn} · @{review_agent}\n\n{review_reply}\n")

        patch_list = extract_patch_list(work_reply, profile.patch_list_headings) or work_reply[:1200]
        if _main_aligned(review_reply):
            aligned = True
            break

    if not aligned:
        close_prompt = (
            f"[项目群讨论 · 收口]\n"
            f"你是 @{review_agent}。双方已讨论 {max_turns} 轮。\n"
            f"请输出最终 `## 定点改稿清单`（work 必须执行的 PATCH 条目，一条一行），"
            f"末行写 `ALIGN: OK` 或说明无法对齐的残留项。\n"
            f"work 最后发言：\n---\n{work_reply}\n---"
        )
        ok, review_reply = collect_agent_reply(review_agent, close_prompt, group_id=group_id)
        if ok:
            publish_group_message(group_id, review_agent, review_reply, route_mentions=False)
            transcript_parts.append(f"## 收口 · @{review_agent}\n\n{review_reply}\n")
            patch_list = extract_patch_list(review_reply, profile.patch_list_headings) or patch_list
            aligned = _main_aligned(review_reply)

    ack_prompt = (
        f"[项目群讨论 · 执行确认]\n"
        f"你是 @{work_agent}。评审最终确认：\n\n---\n{review_reply}\n---\n\n"
        f"用 2–3 段确认你将 **仅按定点改稿清单 PATCH** `{work_task_id}_deliverable.md`"
        f"（不重写其他章节）。复述最终清单。"
    )
    ok, ack_reply = collect_agent_reply(work_agent, ack_prompt, group_id=group_id)
    if ok:
        publish_group_message(group_id, work_agent, ack_reply, route_mentions=False)
        transcript_parts.append(f"## @{work_agent} · 执行确认\n\n{ack_reply}\n")
        if not patch_list:
            patch_list = extract_patch_list(ack_reply, profile.patch_list_headings) or ack_reply[:1000]

    transcript = "\n".join(transcript_parts)
    summary = (
        f"第 {round_num} 轮群讨论对齐（{'已一致' if aligned else '部分一致'}）\n\n"
        f"【定点改稿清单】\n{patch_list}\n\n"
        f"【{review_agent} 确认】\n{review_reply[:800]}"
    )
    save_discussion_artifacts(
        project_id, loop_id, round_num,
        transcript=transcript, summary=summary, patch_list=patch_list,
    )
    status = "已达成一致，将启动定点 PATCH" if aligned else "讨论完成（有残留分歧，仍启动 PATCH）"
    publish_group_message(
        group_id,
        review_agent,
        f"✅ 第 {round_num} 轮群讨论{status}，内核将启动第 {round_num + 1} 轮定点改稿。",
        route_mentions=False,
    )
    return True, summary
