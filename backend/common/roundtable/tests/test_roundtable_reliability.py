#!/usr/bin/env python3
"""圆桌可靠性与上下文压缩测试。"""
from __future__ import annotations

from common.roundtable.roundtable_context import (
    compress_goal_section,
    compress_group_context_text,
    compress_markdown_text,
    compress_message_for_prompt,
    compress_transcript_prior,
    extract_conflict_digest_from_transcript,
    extract_key_bullets,
    extract_turn_digest,
    summarize_transcript_for_prompt,
)
import json
from unittest.mock import patch

from common.roundtable.roundtable_runtime import (
    classify_turn_error,
    collect_roundtable_reply,
    roundtable_session_timeout_seconds,
    roundtable_turn_timeout,
)


def test_collect_roundtable_reply_accepts_thinking_text_events():
    """OpenCode 只发 thinking(type=text) 时也应收集为讨论正文。"""

    def fake_stream(*_args, **_kwargs):
        chunks = [
            {"event": "thinking", "data": {"type": "text", "content": "## 观点\n- 支持 native 记忆\n"}},
            {"event": "done", "data": {"session_id": ""}},
        ]
        for chunk in chunks:
            yield json.dumps(chunk, ensure_ascii=False)

    with patch("base.agent_chat.stream_chat", fake_stream):
        result = collect_roundtable_reply("research", "prompt", None)

    assert result.ok is True
    assert "native 记忆" in result.text


def test_classify_turn_error():
    assert classify_turn_error("Timeout: Agent 'ops' 讨论超时（300s）") == "TIMEOUT"
    assert classify_turn_error("Agent 'dev' 未返回讨论内容") == "EMPTY_REPLY"
    assert classify_turn_error("已取消") == "CANCELLED"


def test_roundtable_turn_timeout_default():
    assert roundtable_turn_timeout() >= 60


def test_session_timeout_scales_with_speakers():
    small = roundtable_session_timeout_seconds(3, 2)
    large = roundtable_session_timeout_seconds(7, 3)
    assert large > small


def test_extract_key_bullets():
    text = "## A\n- 第一点观点非常重要\n- 第二点\n\n段落"
    bullets = extract_key_bullets(text, max_points=5)
    assert bullets
    assert "第一点" in bullets[0]


def test_compress_message_preserves_structure():
    long_body = "## 观点\n" + "- " + ("细节" * 40 + "\n") * 20
    goal = "## Goal\n" + "项目要做 GEO 运营自动化\n" + "第二行目标\n"
    raw = long_body + "\n" + goal
    out = compress_message_for_prompt(raw, max_chars=900)
    assert "## 观点" in out or "观点" in out
    assert "[项目目标摘要]" in out
    assert "GEO" in out or "项目" in out
    assert len(out) <= 900


def test_compress_goal_section_not_empty():
    goal = "line1\n- bullet one\n- bullet two\n" + ("x" * 500)
    summary = compress_goal_section(goal, max_chars=200)
    assert summary
    assert len(summary) <= 200


def test_compress_markdown_keeps_headers():
    text = "## 已共识\n全部同意分离\n\n## 分歧\n" + ("反对点 " * 100)
    out = compress_markdown_text(text, max_chars=400)
    assert "已共识" in out
    assert "分歧" in out


def test_compress_group_context_within_budget():
    lines = [f"@a{i}: " + ("内容" * 200) for i in range(30)]
    ctx = "\n".join(lines)
    out = compress_group_context_text(ctx, total_budget=5000)
    assert len(out) <= 5200
    assert "a29" in out or "较早" in out


def test_compress_transcript_prior():
    long_body = "长文" * 500
    prior = (
        "## [立论 R1] arch (@arch)\n\n"
        "## 观点\n- 第一点\n- 第二点\n\n"
        f"## 我不能接受的点\n- 反对 ops 全自动\n\n{long_body}\n\n"
    ) * 3
    out = compress_transcript_prior(prior, max_chars=3000)
    assert len(out) <= 3100
    assert "我不能接受的点" in out
    assert "要点摘要" in out or len(out) < len(prior) // 2
    assert long_body[:80] not in out


def test_extract_turn_digest_prefers_bullets():
    text = "## 观点\n" + ("废话" * 200) + "\n- 关键结论 A 需要足够长度\n- 关键结论 B 同样需要足够长度\n"
    out = extract_turn_digest(text, max_chars=400)
    assert "关键结论" in out
    assert len(out) <= 400


def test_summarize_transcript_for_prompt():
    raw = (
        "## [立论] arch (@arch)\n\n"
        "## 我不能接受的点\n- 不接受 X\n\n"
        + ("详细论述" * 300)
        + "\n\n## [立论] product (@product)\n\n"
        "## 建议\n- 采用 Y\n"
    )
    out = summarize_transcript_for_prompt(raw, max_chars=2000)
    assert "## [立论]" in out
    assert "不能接受" in out or "不接受" in out
    assert len(out) < len(raw) // 3


def test_extract_conflict_digest_from_transcript():
    raw = (
        "## [立论] arch (@arch)\n\n"
        "## 我不能接受的点\n- 反对全自动\n\n"
        "## [立论] qa (@qa)\n\n"
        "## 观点\n- 仅测试相关\n"
    )
    out = extract_conflict_digest_from_transcript(raw)
    assert "arch" in out
    assert "反对全自动" in out
    assert "qa" not in out or "仅测试" not in out
