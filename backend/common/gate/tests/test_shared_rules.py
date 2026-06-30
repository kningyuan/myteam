#!/usr/bin/env python3
"""团队通用 rules — shared_rules 模块。"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from common.gate.shared_rules import (  # noqa: E402
    list_shared_rule_files,
    read_all_shared_rules,
    read_shared_rule,
    shared_rule_label,
    write_shared_rule,
)


def test_shared_rule_label_known():
    assert shared_rule_label("ethos.md") == "团队哲学"
    assert shared_rule_label("unknown.md") == "unknown"


def test_list_shared_rule_files_includes_ethos():
    files = list_shared_rule_files()
    names = {f["filename"] for f in files}
    assert "ethos.md" in names
    ethos = next(f for f in files if f["filename"] == "ethos.md")
    assert ethos["label"] == "团队哲学"


def test_read_shared_rule_roundtrip(tmp_path, monkeypatch):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    monkeypatch.setattr("common.gate.shared_rules.RULES_DIR", rules_dir)

    write_shared_rule("test-rule.md", "# hello")
    assert read_shared_rule("test-rule.md") == "# hello"
    assert read_all_shared_rules()["test-rule.md"] == "# hello"


def test_validate_filename_rejects_traversal():
    with pytest.raises(ValueError, match="非法"):
        read_shared_rule("../evil.md")
    with pytest.raises(ValueError, match="仅支持"):
        write_shared_rule("bad.txt", "x")
