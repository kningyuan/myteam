#!/usr/bin/env python3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
from common.project_artifacts import (  # noqa: E402
    get_task_deliverable_bundle,
    is_code_project_task,
    read_task_artifact_file,
    scan_project_dir,
    task_project_dir,
)
from common.store import Store  # noqa: E402


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "state.db")
    return store, tmp_path


def test_code_project_task_types():
    assert is_code_project_task("code-deliverable")
    assert is_code_project_task("code-testing")
    assert not is_code_project_task("research")


def test_scan_project_dir(env):
    store, tmp = env
    proj = task_project_dir("pro1", "t1")
    (proj / "README.md").write_text("# demo", encoding="utf-8")
    (proj / "main.py").write_text("print(1)", encoding="utf-8")
    (proj / "output").mkdir()
    (proj / "output" / "run.log").write_text("ok", encoding="utf-8")

    files = scan_project_dir(proj)
    found = {f["path"] for f in files}
    assert "README.md" in found
    assert "main.py" in found
    assert "output/run.log" in found


def test_deliverable_bundle_code_project(env):
    store, tmp = env
    pid = "pro_art"
    store.upsert_project(pid, title="T", status="completed")
    store.upsert_task(pid, "t1", name="dev", agent="developer", task_type="code-deliverable", status="completed")

    proj = task_project_dir(pid, "t1")
    (proj / "README.md").write_text("readme", encoding="utf-8")
    (proj / "collect.sh").write_text("#!/bin/bash", encoding="utf-8")

    bundle = get_task_deliverable_bundle(store, pid, "t1")
    assert bundle["base"] == "code_project"
    assert bundle["project_dir"] == "t1/"
    assert any(f["path"] == "collect.sh" for f in bundle["files"])


def test_read_task_artifact_file_from_project_dir(env):
    store, tmp = env
    pid = "pro_art2"
    store.upsert_project(pid, title="T", status="completed")
    store.upsert_task(pid, "t2", name="test", agent="tester", task_type="code-testing", status="completed")
    proj = task_project_dir(pid, "t2")
    (proj / "tests").mkdir()
    (proj / "tests" / "cases.md").write_text("cases", encoding="utf-8")
    (proj / "run.sh").write_text("echo test", encoding="utf-8")

    data = read_task_artifact_file(store, pid, "t2", "tests/cases.md")
    assert data["exists"] is True
    assert "cases" in data["content"]
