#!/usr/bin/env python3
"""Tests for quality_gate.py — 8-path coverage.

Covers:
  - 5 rule checks: required_sections, min_length, must_include, file_exists
  - 3 error paths: gbrain unavailable, standard page not found, timeout
  - Skipped gate (no standard page)
  - Gate pass (all rules satisfied)
"""
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Fixture: minimal standards page with all rules
SAMPLE_STANDARDS_PAGE = """---
check_rules:
  required_sections:
    - "概述"
    - "方案"
  min_length: 100
  must_include:
    - "实施方案"
  file_exists:
    - "refs/data.csv"
---
# 标准内容
"""


@pytest.fixture
def gate():
    """Create a QualityGate instance."""
    from common.quality_gate import QualityGate
    return QualityGate("pro_test", "code-deliverable")


class TestReadStandards:
    """Test reading standards from gbrain CLI."""

    def test_gbrain_success(self, gate):
        """read_standards returns parsed rules when gbrain returns valid page."""
        with patch.object(gate, "_read_standards_from_local", return_value=None), \
             patch.object(gate, "_run_gbrain_get",
                          return_value=(0, SAMPLE_STANDARDS_PAGE, "")):
            rules = gate.read_standards()
            assert rules is not None
            assert "概述" in rules["required_sections"]
            assert "方案" in rules["required_sections"]
            assert rules["min_length"] == 100
            assert "实施方案" in rules["must_include"]
            assert "refs/data.csv" in rules["file_exists"]

    def test_gbrain_not_found(self, gate):
        """read_standards returns None when gbrain returns empty."""
        with patch.object(gate, "_read_standards_from_local", return_value=None), \
             patch.object(gate, "_run_gbrain_get", return_value=(0, "", "")):
            rules = gate.read_standards()
            assert rules is None

    def test_gbrain_cli_unavailable(self, gate):
        """read_standards returns None when gbrain binary not in PATH."""
        with patch.object(gate, "_read_standards_from_local", return_value=None), \
             patch.object(gate, "_run_gbrain_get",
                          side_effect=FileNotFoundError("gbrain not found")):
            rules = gate.read_standards()
            assert rules is None

    def test_gbrain_timeout(self, gate):
        """read_standards returns None on subprocess timeout."""
        with patch.object(gate, "_read_standards_from_local", return_value=None), \
             patch.object(gate, "_run_gbrain_get",
                          side_effect=subprocess.TimeoutExpired("gbrain", 30)):
            rules = gate.read_standards()
            assert rules is None

    def test_gbrain_error(self, gate):
        """read_standards returns None when gbrain returns non-zero."""
        with patch.object(gate, "_read_standards_from_local", return_value=None), \
             patch.object(gate, "_run_gbrain_get",
                          return_value=(1, "", "error")):
            rules = gate.read_standards()
            assert rules is None


class TestGateCheck:
    """Test the check() method — all rule paths."""

    def test_all_rules_pass(self, gate, tmp_path):
        """All 5 rules pass with valid deliverable."""
        # Create deliverable file with matching content
        d = tmp_path / "deliverables"
        d.mkdir(parents=True)
        df = d / "output.md"
        df.write_text("""
# 概述
这是概述内容

## 方案
这是方案内容

实施方案需要详细说明

## 其他
内容
""", encoding="utf-8")
        # Create referenced file
        ref = d / "refs"
        ref.mkdir()
        (ref / "data.csv").write_text("a,b,c\n1,2,3")

        with patch.object(gate, "read_standards", return_value={
            "required_sections": ["概述", "方案"],
            "min_length": 10,
            "must_include": ["实施方案"],
            "file_exists": ["refs/data.csv"],
        }):
            result = gate.check(str(df))
            assert result.passed is True
            assert len(result.failures) == 0
            assert result.skipped is False

    def test_required_sections_missing(self, gate, tmp_path):
        """Fails when required section is missing."""
        d = tmp_path / "deliverables"
        d.mkdir(parents=True)
        df = d / "output.md"
        df.write_text("# 仅概述\n内容")

        with patch.object(gate, "read_standards", return_value={
            "required_sections": ["概述", "方案"],
            "min_length": 0,
            "must_include": [],
            "file_exists": [],
        }):
            result = gate.check(str(df))
            assert result.passed is False
            assert any(f["rule"] == "required_sections" for f in result.failures)

    def test_min_length_below_threshold(self, gate, tmp_path):
        """Fails when content is too short."""
        d = tmp_path / "deliverables"
        d.mkdir(parents=True)
        df = d / "short.md"
        df.write_text("短")

        with patch.object(gate, "read_standards", return_value={
            "required_sections": [],
            "min_length": 1000,
            "must_include": [],
            "file_exists": [],
        }):
            result = gate.check(str(df))
            assert result.passed is False
            assert any(f["rule"] == "min_length" for f in result.failures)

    def test_must_include_missing(self, gate, tmp_path):
        """Fails when required keyword is missing."""
        d = tmp_path / "deliverables"
        d.mkdir(parents=True)
        df = d / "output.md"
        df.write_text("内容")

        with patch.object(gate, "read_standards", return_value={
            "required_sections": [],
            "min_length": 0,
            "must_include": ["必需的术语"],
            "file_exists": [],
        }):
            result = gate.check(str(df))
            assert result.passed is False
            assert any(f["rule"] == "must_include" for f in result.failures)

    def test_file_exists_missing(self, gate, tmp_path):
        """Fails when referenced file doesn't exist."""
        d = tmp_path / "deliverables"
        d.mkdir(parents=True)
        df = d / "output.md"
        df.write_text("内容")

        with patch.object(gate, "read_standards", return_value={
            "required_sections": [],
            "min_length": 0,
            "must_include": [],
            "file_exists": ["refs/missing.csv"],
        }):
            result = gate.check(str(df))
            assert result.passed is False
            assert any(f["rule"] == "file_exists" for f in result.failures)

    def test_deliverable_not_found(self, gate, tmp_path):
        """Fails when deliverable file doesn't exist."""
        with patch.object(gate, "read_standards", return_value={
            "required_sections": [],
            "min_length": 10,
            "must_include": [],
            "file_exists": [],
        }):
            result = gate.check("/nonexistent/path.md")
            assert result.passed is False

    def test_skipped_no_standards(self, gate, tmp_path):
        """Gate returns skipped=True when no standards page found."""
        with patch.object(gate, "read_standards", return_value=None):
            result = gate.check("/any/path.md")
            assert result.passed is True
            assert result.skipped is True

    def test_gate_with_content_arg(self, gate):
        """check() works with content argument instead of file read."""
        with patch.object(gate, "read_standards", return_value={
            "required_sections": ["议题"],
            "min_length": 0,
            "must_include": [],
            "file_exists": [],
        }):
            result = gate.check("/ignored.md", content="# 议题\n内容")
            assert result.passed is True

    def test_multiple_failures(self, gate, tmp_path):
        """Multiple rule failures are all reported."""
        d = tmp_path / "deliverables"
        d.mkdir(parents=True)
        df = d / "output.md"
        df.write_text("短")

        with patch.object(gate, "read_standards", return_value={
            "required_sections": ["概述", "方案", "结论"],
            "min_length": 500,
            "must_include": ["关键词"],
            "file_exists": [],
        }):
            result = gate.check(str(df))
            assert result.passed is False
            # Should have 4 failures: 3 missing sections + 1 min_length
            assert len(result.failures) == 5  # 3 sections + 1 min_length + 1 must_include


class TestEvidenceUrlGate:
    """动作证据校验 evidence_url：动作型任务须有真实已发布证据。"""

    DELIVERABLE = (
        "# 知乎发布记录\n\n"
        "## 发布平台\n知乎专栏\n\n"
        "## 帖子标题\nGEO优化实战指南\n\n"
        "## 已发布URL\nhttps://zhuanlan.zhihu.com/p/123456789\n\n"
        "## 证据截图\nevidence/post.png\n"
    )

    def _gate(self):
        from common.quality_gate import QualityGate
        return QualityGate("pro_test", "publish-post")

    def test_extract_field_inline_and_section(self):
        from common.quality_gate import _extract_field
        assert _extract_field("帖子标题：abc", "帖子标题") == "abc"
        assert _extract_field("## 帖子标题\nxyz", "帖子标题") == "xyz"

    def test_evidence_pass_when_live_verified(self):
        gate = self._gate()
        standards = {
            "required_sections": [], "min_length": 0, "must_include": [],
            "file_exists": [], "evidence_url": {"host_contains": "zhihu.com", "verify_title": True},
        }
        with patch.object(gate, "read_standards", return_value=standards), \
             patch("common.quality_gate.verify_published_url",
                   return_value=(True, False, "ok")):
            result = gate.check("/ignored.md", content=self.DELIVERABLE)
            assert result.passed is True

    def test_evidence_fail_when_no_url(self):
        gate = self._gate()
        standards = {
            "required_sections": [], "min_length": 0, "must_include": [],
            "file_exists": [], "evidence_url": {"host_contains": "zhihu.com", "verify_title": True},
        }
        with patch.object(gate, "read_standards", return_value=standards):
            result = gate.check("/ignored.md", content="## 已发布URL\n（待补充）")
            assert result.passed is False
            assert any(f["rule"] == "evidence_url" for f in result.failures)

    def test_evidence_fail_when_host_mismatch(self):
        gate = self._gate()
        standards = {
            "required_sections": [], "min_length": 0, "must_include": [],
            "file_exists": [], "evidence_url": {"host_contains": "zhihu.com", "verify_title": True},
        }
        content = "## 已发布URL\nhttps://example.com/p/1"
        with patch.object(gate, "read_standards", return_value=standards):
            result = gate.check("/ignored.md", content=content)
            assert result.passed is False
            assert any(f["rule"] == "evidence_url" for f in result.failures)

    def test_evidence_fail_when_title_not_on_page(self):
        gate = self._gate()
        standards = {
            "required_sections": [], "min_length": 0, "must_include": [],
            "file_exists": [], "evidence_url": {"host_contains": "zhihu.com", "verify_title": True},
        }
        with patch.object(gate, "read_standards", return_value=standards), \
             patch("common.quality_gate.verify_published_url",
                   return_value=(False, False, "页面未找到标题")):
            result = gate.check("/ignored.md", content=self.DELIVERABLE)
            assert result.passed is False
            assert any(f["rule"] == "evidence_url" for f in result.failures)

    def test_evidence_blocked_by_antibot_is_soft_pass(self):
        """被平台反爬/登录墙拦截时无法核实 → 不硬失败（URL形态已是硬证据）。"""
        gate = self._gate()
        standards = {
            "required_sections": [], "min_length": 0, "must_include": [],
            "file_exists": [], "evidence_url": {"host_contains": "zhihu.com", "verify_title": True},
        }
        with patch.object(gate, "read_standards", return_value=standards), \
             patch("common.quality_gate.verify_published_url",
                   return_value=(False, True, "被反爬拦截")):
            result = gate.check("/ignored.md", content=self.DELIVERABLE)
            assert result.passed is True

    def test_evidence_verify_off_skips_live_fetch(self, monkeypatch):
        """EVIDENCE_GATE_VERIFY=0：仅校验 URL 存在，不实时访问。"""
        import common.quality_gate as qg
        monkeypatch.setattr(qg, "EVIDENCE_VERIFY_OFF", True)
        gate = qg.QualityGate("pro_test", "publish-post")
        standards = {
            "required_sections": [], "min_length": 0, "must_include": [],
            "file_exists": [], "evidence_url": {"host_contains": "zhihu.com", "verify_title": True},
        }
        called = {"n": 0}
        def _should_not_call(*a, **k):
            called["n"] += 1
            return (False, "should not be called")
        monkeypatch.setattr(qg, "verify_published_url", _should_not_call)
        with patch.object(gate, "read_standards", return_value=standards):
            result = gate.check("/ignored.md", content=self.DELIVERABLE)
            assert result.passed is True
            assert called["n"] == 0


class TestRunQualityGate:
    """Test the convenience function run_quality_gate()."""

    def test_convenience_function(self, tmp_path):
        """run_quality_gate creates gate and returns result."""
        from common.quality_gate import run_quality_gate
        with patch("common.quality_gate.QualityGate.read_standards",
                   return_value=None):
            result = run_quality_gate("pro_test", "test-type", "/path.md")
            assert result.skipped is True