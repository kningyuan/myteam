#!/usr/bin/env python3
"""群组圆桌讨论模式单元测试。"""
from __future__ import annotations

import pytest

from base.group_manager import (
    DEFAULT_ROUNDTABLE_MAX_ROUNDS,
    MAX_ROUNDTABLE_ROUNDS_CAP,
    MIN_ALIGNMENT_CYCLES_BEFORE_EARLY_CONSENSUS,
    accept_early_consensus,
    consensus_agree_threshold,
    consensus_confirm_passed,
    detect_group_mode,
    extract_agenda,
    format_group_context,
    is_invalid_roundtable_reply,
    is_roundtable_terminate_command,
    latest_roundtable_agenda,
    max_roundtable_rounds_cap,
    parse_best_practice_status,
    parse_consensus_status,
    parse_consensus_vote,
    parse_facilitator_draft_status,
    resolve_roundtable_settings,
    roundtable_participation_rate,
    roundtable_quorum_met,
    roundtable_speaker_order,
    should_extend_roundtable_cycles,
    _build_consensus_confirm_prompt,
    _roundtable_topic_block,
)


def test_detect_roundtable_only_at_all():
    members = ["research", "arch", "product"]
    mentioned = members
    assert detect_group_mode("@all 讨论一下登录方案", mentioned) == "roundtable"
    assert detect_group_mode("@all 完成首页重构任务", mentioned) == "roundtable"


def test_detect_notify_for_specific_mentions():
    members = ["main", "product", "arch"]
    assert detect_group_mode("@main 完成首页重构任务", ["main"]) == "notify"
    assert detect_group_mode("@arch @product 帮我想想这个方案", ["arch", "product"]) == "notify"
    assert detect_group_mode("@arch 这个方案怎么样？", ["arch"]) == "notify"


def test_extract_agenda_strips_mentions():
    members = ["main", "product", "arch"]
    assert extract_agenda("@all 讨论登录流程", members) == "讨论登录流程"


def test_extract_agenda_continue_inherits_prior():
    members = ["main", "product", "arch"]
    prior = "认可main的Workflow v3么？"
    assert extract_agenda("继续", members, prior_agenda=prior) == prior
    assert extract_agenda("@all 接着讨论", members, prior_agenda=prior) == prior
    assert extract_agenda("继续", members, prior_agenda="") == "继续"


def test_latest_roundtable_agenda_skips_continue_placeholder(tmp_path, monkeypatch):
    import base.group_manager as gm

    group_dir = tmp_path / "group_roundtables" / "g_test"
    group_dir.mkdir(parents=True)
    (group_dir / "m_old.md").write_text(
        "# 群组圆桌记录\n群组: t\n议题: 继续\n",
        encoding="utf-8",
    )
    (group_dir / "m_new.md").write_text(
        "# 群组圆桌记录\n群组: t\n议题: 认可main的Workflow v3么？\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gm, "ROUNDTABLE_DIR", tmp_path / "group_roundtables")
    assert latest_roundtable_agenda("g_test") == "认可main的Workflow v3么？"


def test_sanitize_roundtable_public_text():
    from common.roundtable_runtime import sanitize_roundtable_public_text

    raw = (
        "## 投票\nCONSENSUS_VOTE: 同意## Goal\n"
        "- Multi-agent roundtable completed\n\n"
        "Continue if you have next steps, or stop and ask for clarification."
    )
    cleaned = sanitize_roundtable_public_text(raw)
    assert "CONSENSUS_VOTE: 同意" in cleaned
    assert "## Goal" not in cleaned
    assert "Continue if you have next steps" not in cleaned

    glued_consensus = "**CONSENSUS: NEED_MORE**## Goal\n- item\n"
    cleaned2 = sanitize_roundtable_public_text(glued_consensus)
    assert "CONSENSUS: NEED_MORE" in cleaned2
    assert "## Goal" not in cleaned2


def test_parse_consensus_vote_sanitizes_glued_goal_before_parse():
    """投票行与 ## Goal 粘连时，parse 前须经 sanitize（含 transcript 流防御）。"""
    from common.roundtable_runtime import sanitize_roundtable_public_text

    glued = "同意通过。\nCONSENSUS_VOTE: 同意## Goal\n- Validate Workflow v3\n"
    assert parse_consensus_vote(glued) == "agree"
    cleaned = sanitize_roundtable_public_text(glued)
    assert "## Goal" not in cleaned


def test_extract_correction_items_from_workflow_v3_draft():
    from common.roundtable_runtime import extract_correction_items

    draft = """
## 推荐做法（本题最佳实践）

#### 修正项 1：E2E 测试基线提前至 P1 末尾（三角色一致）
- P1 末尾必须产出至少 1 条编排内核完整链路的 E2E 测试
- Gate：测试通过率 100%

#### 修正项 2：token 验收改功能性标准（三角色一致）
- adapter 能提取 + API 能返回 + 前端能展示

#### 修正项 7：Gate 条件量化参照 FRAMEWORK-FREEZE.md 标准
- P4 Gate：逐项列出验收清单
"""
    items = extract_correction_items(draft)
    assert [n for n, _, _ in items] == [1, 2, 7]
    assert "E2E" in items[0][1]
    assert "Gate 条件量化" in items[2][1]


def test_write_best_practice_assessment(tmp_path, monkeypatch):
    from common.roundtable_runtime import write_best_practice_assessment
    import common.paths as paths

    monkeypatch.setattr(paths, "MYTEAM_ROOT", tmp_path)
    draft = (
        "#### 修正项 1：E2E 测试基线提前至 P1 末尾\n"
        "- 可执行两次\n"
        "#### 修正项 2：token 验收改功能性\n"
        "- 三步验收\n"
    )
    path = write_best_practice_assessment(
        agenda="认可 Workflow v3 么？",
        group_name="测试群",
        draft_text=draft,
        transcript_rel_path="business/tasks/group_roundtables/g1/m1.md",
        msg_id="m_1781388407652438",
    )
    assert path is not None
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "修正项 1" in text
    assert "修正项 2" in text
    assert "BEST_PRACTICE: PASSED" in text
    assert (tmp_path / "docs" / "assessments").is_dir()

def test_format_group_context():
    g = {
        "messages": [
            {"sender": "user", "text": "大家好"},
            {"sender": "arch", "text": "我先说", "roundtable": True, "roundtable_phase": "opening"},
        ],
    }
    ctx = format_group_context(g)
    assert "@user: 大家好" in ctx
    assert "[圆桌·opening]" in ctx


def test_roundtable_speaker_order_follows_members_list():
    members = ["research", "product", "arch", "main"]
    assert roundtable_speaker_order(["arch", "product", "research"], members) == [
        "research",
        "product",
        "arch",
    ]


def test_resolve_roundtable_settings_all_members_except_facilitator():
    g = {
        "members": ["research", "arch", "main", "product"],
        "roundtable_facilitator": "main",
    }
    fac, _, participants = resolve_roundtable_settings(g, None)
    assert fac == "main"
    assert participants == ["research", "arch", "product"]


def test_resolve_roundtable_settings_default_facilitator_first_member():
    g = {"members": ["arch", "main", "product", "research"]}
    fac, rounds, participants = resolve_roundtable_settings(g, None)
    assert fac == "arch"
    assert rounds >= DEFAULT_ROUNDTABLE_MAX_ROUNDS
    assert participants == ["main", "product", "research"]


def test_resolve_roundtable_settings_custom_facilitator_and_rounds():
    g = {
        "members": ["arch", "main", "product", "research"],
        "roundtable_facilitator": "product",
        "roundtable_max_rounds": 5,
    }
    fac, rounds, participants = resolve_roundtable_settings(g, None)
    assert fac == "product"
    assert rounds == 5
    assert participants == ["arch", "main", "research"]


def test_parse_consensus_status():
    assert parse_consensus_status("讨论结束 CONSENSUS: YES") == "yes"
    assert parse_consensus_status("CONSENSUS: NEED_MORE 仍有分歧") == "need_more"
    assert parse_consensus_status("暂无标记") == "unknown"


def test_is_invalid_roundtable_reply_detects_trigger_workflow():
    bad = "1. 检查 .trigger 目录\n2. 读取 trigger 文件\n3. 检查 .response 目录"
    assert is_invalid_roundtable_reply(bad) is True
    good = "## 核心观点\n\n应从验收标准与任务输入规范入手提升执行质量。"
    assert is_invalid_roundtable_reply(good) is False


def test_roundtable_quorum_two_thirds(monkeypatch):
    import common.skill_settings as ss

    monkeypatch.setattr(ss, "roundtable_quorum_ratio", lambda default=2 / 3: 2 / 3)
    spoke = {"a": True, "b": True, "c": False}
    assert roundtable_participation_rate(spoke) == pytest.approx(2 / 3)
    assert roundtable_quorum_met(spoke) is True
    spoke2 = {"a": True, "b": False, "c": False}
    assert roundtable_quorum_met(spoke2) is False


def test_accept_early_consensus_disabled():
    spoke_ok = {"a": True, "b": True, "c": False}
    assert accept_early_consensus("yes", spoke_ok, alignment_cycles_completed=1) is False


def test_consensus_agree_threshold():
    assert consensus_agree_threshold(3) == 2
    assert consensus_agree_threshold(4) == 2
    assert consensus_agree_threshold(6) == 3
    assert consensus_agree_threshold(7) == 4


def test_consensus_majority_threshold():
    from base.group_manager import consensus_majority_threshold

    assert consensus_majority_threshold(3) == 2
    assert consensus_majority_threshold(4) == 2


def test_parse_facilitator_draft_status():
    assert parse_facilitator_draft_status("## 共识草案\nCONSENSUS: PROPOSED") == "proposed"
    assert parse_facilitator_draft_status("CONSENSUS: NEED_MORE") == "need_more"
    assert parse_facilitator_draft_status("CONSENSUS: YES") == "proposed"


def test_parse_consensus_vote():
    assert parse_consensus_vote("我认可\nCONSENSUS_VOTE: AGREE") == "agree"
    assert parse_consensus_vote("CONSENSUS_VOTE: 反对\n## 我不能接受的点") == "object"
    assert parse_consensus_vote("CONSENSUS_VOTE: ABSTAIN") == "abstain"
    assert parse_consensus_vote("暂无表态") == "unknown"


def test_consensus_confirm_passed():
    speakers = ["a", "b", "c"]
    assert consensus_confirm_passed(
        {"a": "agree", "b": "agree", "c": "agree"}, speakers,
    ) is True
    assert consensus_confirm_passed(
        {"a": "agree", "b": "agree", "c": "object"}, speakers,
    ) is True
    assert consensus_confirm_passed(
        {"a": "agree", "b": "object", "c": "object"}, speakers,
    ) is False
    assert consensus_confirm_passed(
        {"a": "agree", "b": "agree", "c": "abstain"}, speakers,
    ) is True
    speakers6 = ["a", "b", "c", "d", "e", "f"]
    votes = {s: "agree" for s in speakers6[:4]}
    votes["e"] = "abstain"
    votes["f"] = "abstain"
    assert consensus_confirm_passed(votes, speakers6) is True
    tie_votes = {"a": "agree", "b": "agree", "c": "object", "d": "object"}
    assert consensus_confirm_passed(tie_votes, ["a", "b", "c", "d"]) is False


def test_min_alignment_cycles_constant():
    assert MIN_ALIGNMENT_CYCLES_BEFORE_EARLY_CONSENSUS >= 1


def test_should_extend_roundtable_strict_triggers(monkeypatch):
    import common.skill_settings as ss

    monkeypatch.setattr(ss, "roundtable_quorum_ratio", lambda default=2 / 3: 2 / 3)
    monkeypatch.setattr(ss, "group_discussion_allow_round_extension", lambda default=True: True)
    spoke = {"a": True, "b": True, "c": False}
    assert should_extend_roundtable_cycles(
        consensus_status="need_more",
        cycle=3,
        configured_max=3,
        effective_max=3,
        spoke=spoke,
    ) is True
    assert should_extend_roundtable_cycles(
        consensus_status="yes",
        cycle=3,
        configured_max=3,
        effective_max=3,
        spoke=spoke,
    ) is False
    assert should_extend_roundtable_cycles(
        consensus_status="need_more",
        cycle=2,
        configured_max=3,
        effective_max=3,
        spoke=spoke,
    ) is False
    assert should_extend_roundtable_cycles(
        consensus_status="need_more",
        cycle=3,
        configured_max=3,
        effective_max=max_roundtable_rounds_cap(),
        spoke=spoke,
    ) is False


def test_is_roundtable_terminate_command():
    assert is_roundtable_terminate_command("/终止讨论")
    assert is_roundtable_terminate_command("@all /终止圆桌")
    assert is_roundtable_terminate_command("/stop roundtable please")
    assert not is_roundtable_terminate_command("hello")


def test_roundtable_topic_block_anchors_user_topic():
    block = _roundtable_topic_block("分析 myteam 圆桌现状")
    assert "用户话题" in block
    assert "分析 myteam 圆桌现状" in block
    assert "最佳实践" in block


def test_parse_best_practice_status():
    assert parse_best_practice_status("BEST_PRACTICE: PROPOSED") == "proposed"
    assert parse_best_practice_status("BEST_PRACTICE: NEED_MORE") == "need_more"
    assert parse_best_practice_status("暂无标记") == "unknown"


def test_consensus_confirm_prompt_asks_topic_coverage():
    prompt = _build_consensus_confirm_prompt(
        "测试群",
        "arch",
        "架构师",
        "架构 hint",
        "如何改进圆桌",
        "## 推荐做法\nfoo",
        "ctx",
        round_num=1,
    )
    assert "最佳实践是否充分、正确地回答了用户话题" in prompt
    assert "对用户话题的覆盖判断" in prompt
    assert "本专业交叉验证" in prompt


def test_parse_facilitator_draft_status_topic_answer_heading():
    text = "## 推荐做法（本题最佳实践）\n结论\nBEST_PRACTICE: PROPOSED"
    assert parse_facilitator_draft_status(text) == "proposed"
    legacy = "## 对用户话题的共识回答\n结论\nCONSENSUS: PROPOSED"
    assert parse_facilitator_draft_status(legacy) == "proposed"


def test_reorder_group_members(tmp_path, monkeypatch):
    import base.group_manager as gm

    groups_file = tmp_path / "groups.json"
    groups_file.write_text(
        '{"g1": {"name": "t", "members": ["arch", "product", "research"]}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(gm, "GROUPS_FILE", groups_file)

    ok, msg = gm.reorder_group_members("g1", ["research", "arch", "product"])
    assert ok is True
    groups = gm._load_groups()
    assert groups["g1"]["members"] == ["research", "arch", "product"]

    ok2, _ = gm.reorder_group_members("g1", ["research", "arch"])
    assert ok2 is False
