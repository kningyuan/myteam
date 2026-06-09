#!/usr/bin/env python3
"""I-06 regression_archive 单测。"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts" / "regression"))

import regression_archive as arch  # noqa: E402


@pytest.fixture()
def archive_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MYTEAM_ROOT", str(tmp_path))
    db = tmp_path / "business" / "tasks" / "state.db"
    db.parent.mkdir(parents=True)
    import sqlite3

    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE project (project_id TEXT PRIMARY KEY, status TEXT, meta TEXT);
        CREATE TABLE task (project_id TEXT, task_id TEXT, status TEXT);
        CREATE TABLE interaction (project_id TEXT, interaction_id TEXT, status TEXT);
        CREATE TABLE run_event (id INTEGER PRIMARY KEY, interaction_id TEXT, kind TEXT, payload TEXT);
        CREATE TABLE kernel_job (job_id TEXT PRIMARY KEY, project_id TEXT, status TEXT);
        CREATE TABLE workspace_event (id INTEGER PRIMARY KEY, project_id TEXT, type TEXT);
        INSERT INTO project VALUES ('p1', 'completed', '{}');
        INSERT INTO task VALUES ('p1', 't1', 'completed');
    """)
    conn.commit()
    conn.close()
    yield tmp_path


def test_append_run_record_creates_jsonl(archive_env):
    rec = arch.append_run_record(
        reg_id="REG-02",
        project_id="p1",
        pass_=False,
        kpis={"K1": 0.0, "K8": 1.0},
        repo=archive_env,
    )
    assert rec["run_id"]
    assert rec["reg_id"] == "REG-02"
    ledger = archive_env / "business" / "regression" / "runs.jsonl"
    assert ledger.is_file()
    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["pass"] is False
    assert parsed["kpis"]["K1"] == 0.0


def test_last_pass_run_returns_latest_success(archive_env):
    arch.append_run_record(reg_id="REG-02", project_id="p1", pass_=False, kpis={}, repo=archive_env)
    arch.append_run_record(
        reg_id="REG-02", project_id="p1", pass_=True, kpis={"K1": 1.0}, repo=archive_env
    )
    rec = arch.last_pass_run("REG-02", repo=archive_env)
    assert rec is not None
    assert rec["pass"] is True
    assert rec["kpis"]["K1"] == 1.0


def test_list_runs_filter_by_reg_id(archive_env):
    arch.append_run_record(reg_id="REG-02", project_id="p1", pass_=True, kpis={}, repo=archive_env)
    arch.append_run_record(reg_id="REG-L2", project_id="p1", pass_=False, kpis={}, repo=archive_env)
    assert len(arch.list_runs("REG-02", repo=archive_env)) == 1
    assert len(arch.list_runs(repo=archive_env)) == 2


def test_reg_l2_resume_has_pre_reset_archive():
    """I-06 差距：reg_l2_3role.py resume 路径应在 _reset_reg_project 前调用 append_run_record。
    当前缺失此调用，与 reg_02 行为不一致，违反 I-06"reset 前导出不可变 artifact"原则。
    """
    import ast

    src = (REPO / "scripts/regression/reg_l2_3role.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    has_archive_call = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "append_run_record"
        for node in ast.walk(tree)
    )
    assert has_archive_call, (
        "reg_l2_3role.py 缺少 append_run_record 调用（I-06 gap：resume 路径未在 reset 前归档）"
    )
