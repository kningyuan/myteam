#!/usr/bin/env python3
"""交付物保证层单测。"""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from common.delivery.deliverable_guarantee import (  # noqa: E402
    build_execute_envelope,
    deliverable_has_substance,
    scaffold_markdown_deliverable,
    try_adopt_deliverable_response,
)
from common.gate.registry import FormatSpec  # noqa: E402


def test_scaffold_writes_required_sections(tmp_path):
    spec = FormatSpec(
        task_type="research",
        required_sections=["调研背景", "信息来源", "关键发现", "结论"],
        required_heading_level=2,
    )
    p = tmp_path / "t1_deliverable.md"
    scaffold_markdown_deliverable(p, spec, title="测试报告")
    text = p.read_text(encoding="utf-8")
    assert "## 调研背景" in text
    assert "## 结论" in text
    assert "测试报告" in text


def test_scaffold_omits_task_intent_block(tmp_path):
    spec = FormatSpec(task_type="research", required_sections=["调研背景"], required_heading_level=2)
    p = tmp_path / "t1_deliverable.md"
    scaffold_markdown_deliverable(p, spec, title="报告")
    text = p.read_text(encoding="utf-8")
    assert "任务意图" not in text
    assert "【项目目标】" not in text


def test_deliverable_has_substance_rejects_empty_skeleton(tmp_path):
    spec = FormatSpec(task_type="research", stub_floor=20)
    skeleton = "## 调研背景\n\n## 结论\n"
    assert not deliverable_has_substance(skeleton, spec)


def test_deliverable_has_substance_accepts_filled(tmp_path):
    spec = FormatSpec(task_type="research", stub_floor=20)
    body = "## 调研背景\n\n" + ("内容" * 80) + "\n\n## 结论\n\n" + ("收尾" * 40)
    assert deliverable_has_substance(body, spec)


def test_try_adopt_writes_response_when_file_ready(tmp_path, monkeypatch):
    from common.contracts import InteractionRequest

    base = tmp_path / "deliverables"
    base.mkdir()
    dv = base / "t1_deliverable.md"
    dv.write_text(
        "## 调研背景\n\n" + ("AionUi 是一款本地 Cowork 应用。" * 30) + "\n\n"
        "## 信息来源\n\n| 来源 | 可信度 |\n| GitHub | 高 |\n\n"
        "## 关键发现\n\n发现内容足够长。" * 20 + "\n\n"
        "## 结论\n\n结论段落。" * 20 + "\n",
        encoding="utf-8",
    )
    resp_path = tmp_path / "agent.response"
    req = InteractionRequest(
        interaction_id="p:t1:execute:1",
        kind="execute",
        project_id="p",
        task_id="t1",
        agent_id="research",
        intent="调研",
        input={"deliverable_path": "t1_deliverable.md", "deliverable_base": str(base)},
        constraints={"task_type": "research"},
    )
    adopted = try_adopt_deliverable_response(req, resp_path, req_mtime=0.0)
    assert adopted is not None
    assert resp_path.is_file()
    data = json.loads(resp_path.read_text(encoding="utf-8"))
    assert data["interaction_id"] == "p:t1:execute:1"
    assert data["kind"] == "execute"


def test_build_execute_envelope_contract():
    env = build_execute_envelope(
        interaction_id="x",
        task_type="research",
        rel_path="t1_deliverable.md",
        title="T",
    )
    from common.contracts import validate_response_dict
    ok, _, errs = validate_response_dict(env)
    assert ok, errs
