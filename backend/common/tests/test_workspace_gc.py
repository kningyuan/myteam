"""workspace_gc — agent 工作目录临时文件自动清理。"""
from __future__ import annotations

import time

from common import paths
from common.store import Store
from common.agent_port import reconcile_on_start
from common.submit_result import submit
from common.workspace_gc import (
    gc_orphan_workspace_files,
    gc_project_workspace,
    gc_terminal_interactions,
    gc_workspace,
    remove_interaction_files,
    remove_legacy_task_files,
)


def test_remove_interaction_files(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    agent = "dev"
    ws = paths.workspace_dir(agent)
    trig = paths.trigger_dir(agent)
    resp = paths.response_dir(agent)
    trig.mkdir(parents=True)
    resp.mkdir(parents=True)
    iid = "pro1:t1:execute:1"
    (trig / f"{iid}.request").write_text("{}", encoding="utf-8")
    (resp / f"{iid}.response").write_text("{}", encoding="utf-8")

    assert remove_interaction_files(agent, iid) == 2
    assert not (trig / f"{iid}.request").exists()
    assert not (resp / f"{iid}.response").exists()
    assert ws.is_dir()


def test_gc_terminal_interactions(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    db = tmp_path / "state.db"
    store = Store(db)
    agent = "research"
    paths.trigger_dir(agent).mkdir(parents=True)
    paths.response_dir(agent).mkdir(parents=True)
    iid = "pro_gc:t1:execute:1"
    (paths.trigger_dir(agent) / f"{iid}.request").write_text("{}", encoding="utf-8")
    store.create_interaction(iid, "execute", "pro_gc", task_id="t1", agent_id=agent)
    store.update_interaction(iid, status="done")

    summary = gc_terminal_interactions(store)
    assert summary["files_removed"] >= 1
    assert not (paths.trigger_dir(agent) / f"{iid}.request").exists()
    store.close()


def test_gc_project_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    store = Store(tmp_path / "state.db")
    agent = "main"
    paths.trigger_dir(agent).mkdir(parents=True)
    paths.response_dir(agent).mkdir(parents=True)
    iid = "pro_x:team_config"
    (paths.trigger_dir(agent) / f"{iid}.request").write_text("{}", encoding="utf-8")
    (paths.trigger_dir(agent) / "pro_x_t1.trigger").write_text("legacy", encoding="utf-8")
    store.create_interaction(iid, "team_config", "pro_x", agent_id=agent)
    store.update_interaction(iid, status="done")

    out = gc_project_workspace(store, "pro_x")
    assert out["files_removed"] >= 2
    assert not (paths.trigger_dir(agent) / f"{iid}.request").exists()
    assert not (paths.trigger_dir(agent) / "pro_x_t1.trigger").exists()
    store.close()


def test_gc_orphan_old_files(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    store = Store(tmp_path / "state.db")
    agent = "dev"
    trig = paths.trigger_dir(agent)
    trig.mkdir(parents=True)
    orphan = trig / "orphan_iid.request"
    orphan.write_text("{}", encoding="utf-8")
    out = gc_orphan_workspace_files(store, grace_sec=0)
    assert out["files_removed"] == 1
    assert not orphan.exists()
    store.close()


def test_gc_workspace_combined(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    store = Store(tmp_path / "state.db")
    agent = "dev"
    paths.trigger_dir(agent).mkdir(parents=True)
    iid = "pro2:t1:execute:1"
    (paths.trigger_dir(agent) / f"{iid}.request").write_text("{}", encoding="utf-8")
    store.create_interaction(iid, "execute", "pro2", agent_id=agent, task_id="t1")
    store.update_interaction(iid, status="done")

    summary = gc_workspace(store)
    assert summary["files_removed"] >= 1
    store.close()


def test_gc_skips_timed_out_with_adoptable_response(tmp_path, monkeypatch):
    """timed_out 且磁盘有可采纳响应时，gc 不得删除 .response（防 reconcile 竞态）。"""
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    store = Store(tmp_path / "state.db")
    agent = "dev"
    iid = "pro_race:t1:execute:1"
    paths.trigger_dir(agent).mkdir(parents=True)
    paths.response_dir(agent).mkdir(parents=True)
    (paths.trigger_dir(agent) / f"{iid}.request").write_text("{}", encoding="utf-8")
    body = {
        "interaction_id": iid, "kind": "execute", "status": "ok",
        "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
        "result": {"outcome": {"kind": "artifact",
                               "artifact": {"path": "x.md", "title": "X"}}},
    }
    submit(body, paths.response_dir(agent) / f"{iid}.response")
    store.create_interaction(iid, "execute", "pro_race", task_id="t1", agent_id=agent)
    store.update_interaction(iid, status="timed_out")

    summary = gc_terminal_interactions(store)
    assert summary["files_removed"] == 0
    assert (paths.response_dir(agent) / f"{iid}.response").is_file()
    store.close()


def test_reconcile_before_gc_adopts_timed_out_orphan(tmp_path, monkeypatch):
    """run_kernel 顺序：reconcile 先于 gc，timed_out 孤儿可被回收。"""
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    store = Store(tmp_path / "state.db")
    agent = "dev"
    iid = "pro_ord:t1:execute:1"
    paths.trigger_dir(agent).mkdir(parents=True)
    paths.response_dir(agent).mkdir(parents=True)
    (paths.trigger_dir(agent) / f"{iid}.request").write_text("{}", encoding="utf-8")
    submit({
        "interaction_id": iid, "kind": "execute", "status": "ok",
        "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
        "result": {"outcome": {"kind": "artifact",
                               "artifact": {"path": "x.md", "title": "X"}}},
    }, paths.response_dir(agent) / f"{iid}.response")
    store.create_interaction(iid, "execute", "pro_ord", task_id="t1", agent_id=agent)
    store.update_interaction(iid, status="timed_out")

    reconcile_on_start(store)
    gc_workspace(store)

    assert store.get_interaction(iid)["status"] == "done"
    store.close()
