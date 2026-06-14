#!/usr/bin/env python3
"""project_group_discussion 单元测试。"""
from __future__ import annotations

from common.loop_discussion_runtime import extract_section, load_loop_discussion_profile
from common.loop_discussion_dispatch import dispatch_loop_round_done
from common.project_group_discussion import run_structured_group_discussion
from common.loop_runtime import _inject_loop_vars


def test_inject_prev_round():
    out = _inject_loop_vars(
        "prev={prev_round} round={round}",
        loop_id="ch3_quality_round",
        round_num=3,
        max_rounds=5,
    )
    assert out == "prev=2 round=3"


def test_extract_review_sections():
    text = """# 评审

## 审计结论

放行

## 发现与分级

无阻塞项

## 修订要求

无

REVIEW: PASS
"""
    assert "放行" in extract_section(text, "审计结论")
    assert "无阻塞项" in extract_section(text, "发现与分级")


def test_extract_patch_list_from_reply():
    from common.loop_discussion_runtime import extract_patch_list

    text = """讨论回复

## 定点改稿清单

| 小节 | 改法 |
|------|------|
| ### 优势分析 | 补充来源 |
"""
    patch = extract_patch_list(text, ["定点改稿清单", "改稿清单"])
    assert "优势分析" in patch


def test_run_structured_group_discussion_extracts_patch_list(tmp_path, monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_collect(agent_id: str, prompt: str, *, group_id: str = ""):
        calls.append((agent_id, prompt[:40]))
        return True, f"reply from {agent_id}"

    def fake_publish(group_id: str, sender: str, text: str, *, route_mentions: bool):
        calls.append((sender, text[:30]))

    monkeypatch.setattr(
        "common.loop_discussion_runtime.collect_agent_reply", fake_collect,
    )
    monkeypatch.setattr(
        "common.loop_discussion_runtime.publish_group_message", fake_publish,
    )
    monkeypatch.setattr(
        "common.loop_discussion_runtime.PROJECTS_DIR", tmp_path / "tasks" / "project",
    )

    profile = load_loop_discussion_profile("work-review-alignment")
    assert profile is not None
    ok, summary = run_structured_group_discussion(
        "p1", "g1", "ch3_quality_round", 1,
        review_task_id="ch3_quality_round-r1-review",
        work_task_id="ch3_quality_round-r1-work",
        findings="问题 A", revisions="改 X",
        profile=profile,
    )
    assert ok and ("定点改稿清单" in summary or "reply from" in summary)
    assert calls[0][0] == "main"
    assert (tmp_path / "tasks" / "project" / "p1" / "deliverables"
            / "ch3_quality_round-r1-group_discussion.md").is_file()


def test_facilitate_fail_triggers_discussion_when_enabled(monkeypatch):
    triggered = {"n": 0}

    def fake_run(*a, **k):
        triggered["n"] += 1
        return True, "aligned"

    profile = load_loop_discussion_profile("work-review-alignment")

    monkeypatch.setattr(
        "common.loop_discussion_dispatch.group_enabled", lambda *a, **k: True,
    )
    monkeypatch.setattr(
        "common.loop_discussion_dispatch.find_project_group",
        lambda pid: {"id": "g1"},
    )
    monkeypatch.setattr(
        "common.loop_discussion_dispatch.read_deliverable",
        lambda pid, tid: "## 审计结论\n\n需修订\n\n## 修订要求\n\n改架构\n\nREVIEW: FAIL",
    )
    monkeypatch.setattr(
        "common.loop_discussion_dispatch.workflow_group_discussion_enabled",
        lambda pid: True,
    )
    monkeypatch.setattr(
        "common.loop_discussion_dispatch.load_loop_discussion_profile",
        lambda pid: profile,
    )
    monkeypatch.setattr(
        "common.loop_discussion_dispatch.load_business_hook",
        lambda name: type("H", (), {"run_structured_group_discussion": fake_run})(),
    )
    monkeypatch.setattr(
        "common.loop_discussion_dispatch.publish_group_message", lambda *a, **k: None,
    )

    dispatch_loop_round_done(
        "p1", "ch3_quality_round", 1,
        passed=False,
        work_task_id="ch3_quality_round-r1-work",
        review_task_id="ch3_quality_round-r1-review",
        max_rounds=5,
        profile=profile,
    )
    assert triggered["n"] == 1
