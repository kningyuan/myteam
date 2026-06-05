#!/usr/bin/env python3
"""Phase 4 Gate + 格式注册表测试（D14 / D15）。

验证标准：同一 task_type 的「下发约束」与「门禁判定」出自同一注册表；
action 任务证据校验生效；min_length 降为防 stub、must_include 默认关。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.gate import check_contract, check_execute, check_format  # noqa: E402
from common.registry import FormatSpec, get_spec, is_stub, load_registry  # noqa: E402


# ── 注册表：单一出处 ─────────────────────────────────────────


def test_registry_loads_real_types():
    reg = load_registry()
    assert "research" in reg and "publish-post" in reg
    assert get_spec("research").outcome_kind == "artifact"
    assert get_spec("publish-post").outcome_kind == "action"  # 有 evidence_url → action
    assert get_spec("code-deliverable").outcome_kind == "code_project"


def test_code_project_gate(tmp_path):
    proj = tmp_path / "t1"
    proj.mkdir()
    (proj / "README.md").write_text("readme", encoding="utf-8")
    (proj / "main.sh").write_text("#!/bin/bash", encoding="utf-8")
    env = {
        "interaction_id": "i1", "kind": "execute", "status": "ok",
        "quality": {"score": 0.9, "known_gaps": [], "notes": "ok"},
        "meta": {"task_type": "code-deliverable", "task_id": "t1"},
        "result": {"outcome": {"kind": "artifact",
                               "artifact": {"path": "t1/", "format": "code_project"}}},
    }
    res = check_execute(env, base_dir=str(tmp_path))
    assert res.passed


def test_registry_acceptance_criteria_shared():
    spec = get_spec("research")
    assert spec.acceptance_criteria  # 自评+评审共用，非空


def test_is_stub():
    assert is_stub("")
    assert is_stub("   ")
    assert is_stub("TODO", floor=20)
    assert not is_stub("这是一段足够长的具体内容，覆盖了实际要点和细节说明。", floor=20)


# ── 格式门禁 ─────────────────────────────────────────────────


def _research_spec() -> FormatSpec:
    return get_spec("research")


def test_format_pass(tmp_path):
    content = (
        "# 报告\n\n## 调研背景\n这是足够具体的背景说明，包含目的范围与方法。\n\n"
        "## 信息来源\n| 来源 | 可信度 |\n|---|---|\n| A | 高 |\n\n"
        "## 关键发现\n发现一：依据……\n\n## 结论\n建议……\n"
    )
    res = check_format(_research_spec(), content)
    assert res.passed, res.failures


def test_format_missing_section():
    content = "# 报告\n\n## 调研背景\n足够具体的内容说明在这里展开论述。\n"
    res = check_format(_research_spec(), content)
    assert not res.passed
    rules = {f["rule"] for f in res.failures}
    assert "required_sections" in rules


def test_format_stub_rejected():
    res = check_format(_research_spec(), "## 调研背景\n## 信息来源\n## 关键发现\n## 结论\nTODO")
    assert not res.passed
    assert any(f["rule"] == "stub" for f in res.failures)


def test_must_include_off_by_default():
    # research 的 must_include 含「数据来源」「可信度」；默认关 → 不因缺关键词失败
    content = (
        "# R\n\n## 调研背景\n足够具体的背景内容说明在此展开。\n\n## 信息来源\n来源若干。\n\n"
        "## 关键发现\n发现内容。\n\n## 结论\n结论内容。\n"
    )
    assert check_format(_research_spec(), content).passed
    on = check_format(_research_spec(), content, enforce_must_include=True)
    assert not on.passed and any(f["rule"] == "must_include" for f in on.failures)


# ── 契约门禁 ─────────────────────────────────────────────────


def test_contract_gate_rejects_bad():
    assert not check_contract({"interaction_id": "x", "kind": "task_plan", "result": {}}).passed


# ── execute 串联（artifact / action）─────────────────────────


def _execute_envelope(outcome):
    return {
        "interaction_id": "i1", "kind": "execute", "status": "ok",
        "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
        "meta": {"task_type": "research"},
        "result": {"outcome": outcome},
    }


def test_check_execute_artifact_ok(tmp_path):
    dv = tmp_path / "deliverables" / "r.md"
    dv.parent.mkdir(parents=True)
    dv.write_text(
        "# R\n\n## 调研背景\n足够具体的背景内容在此展开说明。\n\n## 信息来源\n来源。\n\n"
        "## 关键发现\n发现。\n\n## 结论\n结论。\n", encoding="utf-8")
    env = _execute_envelope({"kind": "artifact",
                             "artifact": {"path": "deliverables/r.md", "title": "R"}})
    res = check_execute(env, base_dir=str(tmp_path))
    assert res.passed, res.failures


def test_check_execute_missing_file(tmp_path):
    env = _execute_envelope({"kind": "artifact",
                             "artifact": {"path": "deliverables/nope.md", "title": "R"}})
    res = check_execute(env, base_dir=str(tmp_path))
    assert not res.passed and any(f["rule"] == "file_exists" for f in res.failures)


def test_check_execute_action_evidence(tmp_path):
    dv = tmp_path / "deliverables" / "rec.md"
    dv.parent.mkdir(parents=True)
    # publish-post 必需章节 + 合规 URL + 截图存在
    (tmp_path / "deliverables" / "evidence").mkdir(parents=True)
    (tmp_path / "deliverables" / "evidence" / "a.png").write_text("x")
    dv.write_text(
        "# 发布记录\n\n## 发布平台\n知乎\n\n## 帖子标题\nGEO 实战\n\n"
        "## 已发布URL\nhttps://zhuanlan.zhihu.com/p/123\n\n"
        "## 证据截图\nevidence/a.png\n", encoding="utf-8")
    env = {
        "interaction_id": "i1", "kind": "execute", "status": "ok",
        "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
        "meta": {"task_type": "publish-post"},
        "result": {"outcome": {
            "kind": "action",
            "artifact": {"path": "deliverables/rec.md", "title": "发布记录"},
            "evidence": {"action_type": "publish",
                         "url": "https://zhuanlan.zhihu.com/p/123",
                         "screenshots": ["evidence/a.png"]},
        }},
    }
    res = check_execute(env, base_dir=str(tmp_path))
    assert res.passed, res.failures


def test_check_execute_action_missing_url(tmp_path):
    dv = tmp_path / "deliverables" / "rec.md"
    dv.parent.mkdir(parents=True)
    dv.write_text(
        "# 发布记录\n\n## 发布平台\n知乎\n\n## 帖子标题\nT\n\n## 已发布URL\n（未发布）\n\n"
        "## 证据截图\n无\n", encoding="utf-8")
    env = {
        "interaction_id": "i1", "kind": "execute", "status": "ok",
        "quality": {"score": 0.5, "known_gaps": ["未发布"], "notes": ""},
        "meta": {"task_type": "publish-post"},
        "result": {"outcome": {
            "kind": "action",
            "artifact": {"path": "deliverables/rec.md", "title": "rec"},
            "evidence": {"action_type": "publish", "url": "https://x", "screenshots": []},
        }},
    }
    res = check_execute(env, base_dir=str(tmp_path))
    assert not res.passed and any(f["rule"] == "evidence_url" for f in res.failures)
