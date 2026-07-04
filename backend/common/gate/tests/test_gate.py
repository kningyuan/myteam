#!/usr/bin/env python3
"""Phase 4 Gate + 格式注册表测试（D14 / D15）。

验证标准：同一 task_type 的「下发约束」与「门禁判定」出自同一注册表；
action 任务证据校验生效；min_length 降为防 stub、must_include 默认关。
"""
import sys
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.gate.gate import (  # noqa: E402
    _extract_field,
    check_contract,
    check_execute,
    check_format,
    verify_published_url,
)
from common.gate.registry import FormatSpec, get_spec, is_stub, load_registry, resolve_format_spec  # noqa: E402


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
    # research 的约束/验收标准绑在默认模板 research-report 上，经 resolve_format_spec 回退拿到
    spec = resolve_format_spec("research")
    assert spec is not None
    assert spec.acceptance_criteria  # 自评+评审共用，非空


def test_is_stub():
    assert is_stub("")
    assert is_stub("   ")
    assert is_stub("TODO", floor=20)
    assert not is_stub("这是一段足够长的具体内容，覆盖了实际要点和细节说明。", floor=20)


# ── 格式门禁 ─────────────────────────────────────────────────


def _research_spec() -> FormatSpec:
    # research 约束绑默认模板 research-report，经 resolve_format_spec 回退拿到（含矩阵/维度/来源/推断）
    spec = resolve_format_spec("research")
    assert spec is not None
    return spec


def test_format_pass(tmp_path):
    # research-report 模板已强化约束（矩阵/维度/来源/推断），样本须满足全部约束
    content = (
        "# 报告\n\n## 调研背景\n这是足够具体的背景说明，包含目的范围与方法，"
        "覆盖核心功能、用户画像、变现模式、用户评价四个维度的调研框架。\n\n"
        "## 信息来源\n| 来源 | 可信度 |\n|---|---|\n| [S1] 官网 | 高 |\n| [S2] 测评 | 中 |\n\n"
        "## 关键发现\n"
        "| 对象 | 核心功能 | 用户画像 | 变现模式 | 用户评价 |\n|---|---|---|---|---|\n"
        "| A | 功能X [S1] | 画像P [S2] | 订阅制 [S1] | 好评 [S2] |\n"
        "| B | 功能Y [S2] | 画像Q [S1] | 广告 [S1] | 中评 [S2] |\n\n"
        "核心功能方面，A 与 B 均支持基础编辑；用户画像显示 A 偏专业用户。\n\n"
        "## 结论\n建议 P0：优先对齐 A 的核心功能；P1：参考 B 的变现模式。\n"
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
    # research-report 模板已强化约束；样本须满足矩阵/维度/来源/stub 约束
    content = (
        "# R\n\n## 调研背景\n足够具体的背景内容说明在此展开，覆盖核心功能、用户画像、"
        "变现模式、用户评价四维度的调研目的与范围。\n\n"
        "## 信息来源\n| 来源 | 可信度 |\n|---|---|\n| [S1] A | 高 |\n\n"
        "## 关键发现\n"
        "| 对象 | 核心功能 | 用户画像 | 变现模式 | 用户评价 |\n|---|---|---|---|---|\n"
        "| A | X [S1] | P [S1] | 订阅 [S1] | 好 [S1] |\n\n"
        "核心功能与用户画像均有数据支撑。\n\n"
        "## 结论\n结论内容。\n"
    )
    assert check_format(_research_spec(), content).passed


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
    # research-report 模板已强化约束：样本须满足矩阵/维度/来源/stub
    dv.write_text(
        "# R\n\n## 调研背景\n足够具体的背景内容在此展开说明，覆盖核心功能、用户画像、"
        "变现模式、用户评价四维度调研目的与范围。\n\n"
        "## 信息来源\n| 来源 | 可信度 |\n|---|---|\n| [S1] A | 高 |\n\n"
        "## 关键发现\n"
        "| 对象 | 核心功能 | 用户画像 | 变现模式 | 用户评价 |\n|---|---|---|---|---|\n"
        "| A | X [S1] | P [S1] | 订阅 [S1] | 好 [S1] |\n\n"
        "核心功能与用户画像均有数据支撑。\n\n"
        "## 结论\n结论内容。\n", encoding="utf-8")
    # research 用 light_v1 profile：须有 align.md + verify.log 过程产物
    (tmp_path / "align.md").write_text(
        "对齐：本任务覆盖核心功能、用户画像、变现模式、用户评价四维度竞品调研，产出结构化报告。", encoding="utf-8")
    (tmp_path / "verify.log").write_text("verify: sections ok, matrix ok, sources ok, dimensions ok", encoding="utf-8")
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
    # 不测 live 知乎页：只验 Gate 结构 + URL/截图；标题核对由 verify_published_url 单测覆盖
    with patch("common.gate.gate.verify_published_url", return_value=(True, False, "mock ok")):
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


# ── 证据工具（原 quality_gate 迁入 gate）────────────────────


def test_extract_field_inline_and_section():
    assert _extract_field("帖子标题：abc", "帖子标题") == "abc"
    assert _extract_field("## 帖子标题\nxyz", "帖子标题") == "xyz"


def test_verify_published_url_no_browse_returns_blocked(monkeypatch):
    monkeypatch.setattr("common.gate.gate._resolve_browse_bin", lambda: None)
    verified, blocked, detail = verify_published_url("https://example.com/p/1", "标题")
    assert not verified
    assert blocked
    assert "browse" in detail.lower() or "无法" in detail
