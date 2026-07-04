#!/usr/bin/env python3
"""workflow-creator 工具链测试 — P4a/b/c。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from business.scripts.validate_workflow import validate_workflow_id, validate_workflow_file


def test_validate_workflow_id_pass():
    """已存在且合法的 workflow 校验通过。"""
    ok, msg = validate_workflow_id("competitive-research")
    assert ok
    assert "校验通过" in msg


def test_validate_workflow_id_plan_improve_pass():
    """方案完善 workflow（含 loop）校验通过。"""
    ok, msg = validate_workflow_id("方案完善")
    assert ok
    assert "loops" in msg


def test_validate_workflow_id_missing_fails():
    """不存在的 workflow id 校验失败。"""
    ok, msg = validate_workflow_id("no-such-workflow-xyz")
    assert not ok
    assert "未找到" in msg or "不存在" in msg


def test_validate_workflow_file_pass(tmp_path):
    """按文件路径校验合法 workflow。"""
    src = Path("business/workflows/competitive-research.yaml")
    fp = tmp_path / "test-wf.yaml"
    fp.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    ok, msg = validate_workflow_file(str(fp))
    assert ok
    assert "校验通过" in msg


def test_validate_workflow_file_not_found():
    """文件不存在时校验失败。"""
    ok, msg = validate_workflow_file("/no/such/file.yaml")
    assert not ok
    assert "不存在" in msg


def test_validate_workflow_rejects_invalid_yaml(tmp_path):
    """非法 workflow（task_type 未注册）校验失败。"""
    fp = tmp_path / "bad-wf.yaml"
    fp.write_text(
        "id: bad-wf\nname: bad\nversion: '1.0'\n"
        "tasks:\n  - id: t1\n    agent: research\n    task_type: no-such-type\n    dependencies: []\n",
        encoding="utf-8",
    )
    ok, msg = validate_workflow_file(str(fp))
    assert not ok
    assert "未知 task_type" in msg or "校验失败" in msg or "未注册" in msg
