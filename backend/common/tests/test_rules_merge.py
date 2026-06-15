#!/usr/bin/env python3
"""rules_merge profile 加载测试。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.rules_merge import merge_rules_file, normalize_rules_profile  # noqa: E402


@pytest.fixture()
def rules_env(tmp_path, monkeypatch):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "universal-rules.md").write_text("# universal\n", encoding="utf-8")
    (rules_dir / "interactive-guide.md").write_text("# interactive\n", encoding="utf-8")
    (rules_dir / "brainstorming-guide.md").write_text("# brainstorm\n", encoding="utf-8")
    (rules_dir / "worker-template.md").write_text("# worker\n", encoding="utf-8")
    ws = tmp_path / "workspaces" / "arch"
    ws.mkdir(parents=True)
    (ws / "AGENTS.md").write_text("# role\n", encoding="utf-8")
    return rules_dir, str(ws)


def test_interactive_profile(rules_env):
    rules_dir, ws = rules_env
    path = merge_rules_file("arch", ws, rules_dir, profile="interactive")
    assert path
    text = Path(path).read_text(encoding="utf-8")
    assert "interactive" in text
    assert "brainstorm" not in text
    assert "worker" not in text
    assert "role" not in text


def test_conversation_aliases_interactive(rules_env):
    rules_dir, ws = rules_env
    path = merge_rules_file("arch", ws, rules_dir, profile="conversation")
    assert path
    text = Path(path).read_text(encoding="utf-8")
    assert "interactive" in text
    assert normalize_rules_profile("conversation") == "interactive"


def test_discussion_profile(rules_env):
    rules_dir, ws = rules_env
    path = merge_rules_file("arch", ws, rules_dir, profile="discussion")
    assert path
    text = Path(path).read_text(encoding="utf-8")
    assert "brainstorm" in text
    assert "interactive" not in text
    assert "worker" not in text
    assert "role" not in text


def test_workflow_execute_profile(rules_env):
    rules_dir, ws = rules_env
    path = merge_rules_file("arch", ws, rules_dir, profile="workflow_execute")
    assert path
    text = Path(path).read_text(encoding="utf-8")
    assert "worker" in text
    assert "role" in text
    assert "brainstorm" not in text
    assert "interactive" not in text


def test_main_skips_worker_template_on_execute(rules_env):
    rules_dir, ws = rules_env
    path = merge_rules_file("main", ws, rules_dir, profile="workflow_execute")
    assert path
    text = Path(path).read_text(encoding="utf-8")
    assert "worker" not in text
    assert "role" not in text
