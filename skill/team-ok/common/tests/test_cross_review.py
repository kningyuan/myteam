#!/usr/bin/env python3
"""Tests for cross_review.py.

Covers:
  - Handoff document creation
  - Reviewer notification
  - Successful review (reviewer responds in time)
  - Review rejection (reviewer says not passed)
  - Review timeout (300s → needs_review)
  - No reviewer assigned (skip)
  - Reviewer notification failure
"""
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestWriteHandoffDoc:
    """Test handoff document creation."""

    def test_handoff_created(self, tmp_path, monkeypatch):
        """_write_handoff_doc creates file with correct content."""
        from common.cross_review import _write_handoff_doc
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        path = _write_handoff_doc("pro_001", "task_01", "tester",
                                  "/deliverables/output.md", "已完成任务")
        assert Path(path).exists()
        content = Path(path).read_text(encoding="utf-8")
        assert "task_01" in content
        assert "tester" in content
        assert "已完成任务" in content


class TestNotifyReviewer:
    """Test reviewer notification."""

    def test_notify_success(self, tmp_path, monkeypatch):
        """_notify_reviewer creates trigger file."""
        from common.cross_review import _notify_reviewer
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        result = _notify_reviewer("pro_001", "tester", "task_01", "/handoff.md")
        assert result is True

        # Verify trigger file was created
        trigger_file = (tmp_path / ".openclaw" / "workspace-tester"
                        / ".trigger" / "pro_001_task_01_review.request")
        assert trigger_file.exists()
        data = json.loads(trigger_file.read_text())
        assert data["event"] == "cross_review"
        assert data["task_id"] == "task_01"

    def test_notify_no_reviewer(self, tmp_path, monkeypatch):
        """_notify_reviewer returns True when reviewer is empty."""
        from common.cross_review import _notify_reviewer
        result = _notify_reviewer("pro_001", "", "task_01", "/handoff.md")
        assert result is True  # Empty reviewer returns True


class TestRunCrossReview:
    """Test run_cross_review function."""

    def test_no_reviewer_skipped(self, tmp_path, monkeypatch):
        """run_cross_review skips when no reviewer assigned."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        from common.cross_review import run_cross_review

        result = run_cross_review("pro_001", "task_01", "",
                                  "/deliverables/output.md", "摘要")
        assert result.passed is True
        assert result.skipped is True

    def test_reviewer_passed(self, tmp_path, monkeypatch):
        """run_cross_review returns passed when reviewer approves."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        from common.cross_review import run_cross_review

        # Create the response file immediately
        resp_dir = tmp_path / ".openclaw" / "workspace-main" / ".response"
        resp_dir.mkdir(parents=True)
        resp_file = resp_dir / "pro_001_task_01_review.response"
        resp_file.write_text(json.dumps({"passed": True, "feedback": "LGTM"}))

        with patch("common.cross_review.time.sleep"):  # Don't actually sleep
            result = run_cross_review("pro_001", "task_01", "tester",
                                      "/deliverables/output.md", "摘要")
            assert result.passed is True
            assert result.timed_out is False

    def test_reviewer_rejected(self, tmp_path, monkeypatch):
        """run_cross_review returns not passed when reviewer rejects."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        from common.cross_review import run_cross_review

        resp_dir = tmp_path / ".openclaw" / "workspace-main" / ".response"
        resp_dir.mkdir(parents=True)
        resp_file = resp_dir / "pro_001_task_01_review.response"
        resp_file.write_text(json.dumps({
            "passed": False,
            "feedback": "缺少测试覆盖",
        }))

        with patch("common.cross_review.time.sleep"):
            result = run_cross_review("pro_001", "task_01", "tester",
                                      "/deliverables/output.md", "摘要")
            assert result.passed is False
            assert result.timed_out is False
            assert "测试覆盖" in result.feedback

    def test_review_timeout(self, tmp_path, monkeypatch):
        """run_cross_review returns timed_out after 300s."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        from common.cross_review import run_cross_review

        with (
            patch("common.cross_review.time.sleep"),
            patch("common.cross_review.time.time") as mock_time,
        ):
            # First call to time.time() = 100, second call = 999 (> deadline)
            mock_time.side_effect = [100.0, 999.0]
            result = run_cross_review("pro_001", "task_01", "tester",
                                      "/deliverables/output.md", "摘要")
            assert result.timed_out is True
            assert result.passed is False

    def test_notification_failure_skips(self, tmp_path, monkeypatch):
        """run_cross_review skips when notification fails."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        from common.cross_review import run_cross_review

        with patch("common.cross_review._notify_reviewer", return_value=False):
            result = run_cross_review("pro_001", "task_01", "tester",
                                      "/deliverables/output.md", "摘要")
            assert result.passed is True
            assert result.skipped is True