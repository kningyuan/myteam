#!/usr/bin/env python3
"""子模块协作联动测试：loop → roundtable。

验证协作链路：
  1. loop_discussion_runtime.read_deliverable + extract_section 从评审交付物提取
     「审计结论 / 发现与分级 / 修订要求」三段
  2. loop_discussion_dispatch.dispatch_loop_round_done 把这三段拼成群消息 body 并发布
  3. roundtable_runtime.sanitize_roundtable_public_text 能净化该 body（去掉 checkpoint 泄漏）
  4. roundtable_runtime.extract_correction_items 能从含「修正项 N」的草案文本提取结构化条目

接口契约：loop 产出的评审摘要文本能被 roundtable 消费（净化 / 抽取修正项）。
"""
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
from common.loop.loop_discussion_dispatch import dispatch_loop_round_done  # noqa: E402
from common.loop.loop_discussion_runtime import (  # noqa: E402
    LoopDiscussionProfile,
    extract_section,
    read_deliverable,
)
from common.roundtable.roundtable_runtime import (  # noqa: E402
    extract_correction_items,
    sanitize_roundtable_public_text,
)


@pytest.fixture()
def dispatched_messages():
    """捕获 publish_group_message 发出的群消息。"""
    sent: list[tuple[str, str, str]] = []

    def fake_publish(group_id, sender, text, *, route_mentions):
        sent.append((group_id, sender, text))

    return sent, fake_publish


def _make_review_deliverable(project_dir: Path, task_id: str) -> None:
    """造一份评审交付物，包含 loop 讨论关心的三个章节。"""
    dv = project_dir / "deliverables" / f"{task_id}_deliverable.md"
    dv.parent.mkdir(parents=True, exist_ok=True)
    dv.write_text(
        "# 评审报告\n\n"
        "## 审计结论\n需修订\n\n"
        "## 发现与分级\n- 🔴 章节缺失\n- 🟡 引用不全\n\n"
        "## 修订要求\n1. 补全「调研背景」\n2. 标注数据来源\n",
        encoding="utf-8",
    )


def _profile() -> LoopDiscussionProfile:
    return LoopDiscussionProfile(
        id="work-review-alignment",
        hook_module="work_review_alignment",
        work_agent="product",
        review_agent="main",
        round_summary_label="评审",
        review_sections={
            "conclusion": "审计结论",
            "findings": "发现与分级",
            "revisions": "修订要求",
        },
        pass_marker="REVIEW: PASS",
        fail_marker="REVIEW: FAIL",
    )


def test_loop_extracts_review_sections(tmp_path, monkeypatch):
    """loop_discussion_runtime 能从交付物读出三段评审摘要（roundtable 上游输入）。"""
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    _make_review_deliverable(tmp_path / "project" / "pro_lr", "rv-task")

    text = read_deliverable("pro_lr", "rv-task")
    assert "评审报告" in text
    # extract_section 与 dispatch 内部使用的同一函数
    assert "需修订" in extract_section(text, "审计结论")
    assert "章节缺失" in extract_section(text, "发现与分级")
    assert "补全" in extract_section(text, "修订要求")


def test_dispatch_publishes_body_consumable_by_roundtable(tmp_path, monkeypatch, dispatched_messages):
    """dispatch 把 loop 提取的摘要拼成 body 发布；roundtable 能净化该 body。"""
    sent, fake_publish = dispatched_messages
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    _make_review_deliverable(tmp_path / "project" / "pro_lr", "rv-task")

    # 桩掉 dispatch 依赖的外部入口，保留 read_deliverable/extract_section 真实逻辑
    monkeypatch.setattr("common.loop.loop_discussion_dispatch.group_enabled", lambda pid: True)
    monkeypatch.setattr(
        "common.loop.loop_discussion_dispatch.find_project_group",
        lambda pid: {"id": "g1", "name": "项目群"},
    )
    monkeypatch.setattr("common.loop.loop_discussion_dispatch.publish_group_message", fake_publish)
    monkeypatch.setattr(
        "common.loop.loop_discussion_dispatch.workflow_discussion_profile_id", lambda pid: "p1",
    )
    monkeypatch.setattr(
        "common.loop.loop_discussion_dispatch.load_loop_discussion_profile", lambda pid: _profile(),
    )
    # passed=False 触发非通过分支（会再发一条提示消息）
    dispatch_loop_round_done(
        "pro_lr", "lr", round_num=1, passed=False,
        work_task_id="wk", review_task_id="rv-task", max_rounds=3,
    )

    # 至少发了 1 条群消息，body 含 loop 提取的结论/发现
    assert sent, "dispatch 未发布群消息"
    body = sent[0][2]
    assert "第 1/3 轮" in body
    assert "需修订" in body            # 来自 loop 的 extract_section(审计结论)
    assert "章节缺失" in body          # 来自 loop 的 extract_section(发现与分级)
    assert "rv-task" in body

    # roundtable 消费该 body：sanitize 不破坏关键中文内容，且去掉 checkpoint 泄漏
    cleaned = sanitize_roundtable_public_text(body)
    assert "需修订" in cleaned
    assert "Continue if you have next steps" not in cleaned


def test_roundtable_extracts_corrections_from_loop_draft():
    """loop 草案含「修正项 N」时，roundtable 能抽取结构化条目（接口契约）。"""
    draft = (
        "# 最佳实践草案\n\n"
        "#### 修正项 1: 补全章节\n把「调研背景」写满 200 字。\n\n"
        "#### 修正项 2: 标注来源\n每条数据附链接。\n\n"
    )
    items = extract_correction_items(draft)
    assert len(items) == 2
    nums = [n for n, _, _ in items]
    assert nums == [1, 2]
    assert "补全章节" in items[0][1]
    assert "标注来源" in items[1][1]
