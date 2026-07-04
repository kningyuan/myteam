#!/usr/bin/env python3
"""项目删除（DB + 文件系统临时件）测试。"""
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
from common.store.store import Store  # noqa: E402


def test_delete_project_cleans_db_and_workspace_files(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "ws")
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "proj")
    import common.project.project_admin as admin

    store = Store(tmp_path / "state.db")
    iid = "pro_del:task_001:execute:1"
    store.upsert_project("pro_del", title="待删")
    store.create_interaction(iid, "execute", "pro_del", task_id="task_001", agent_id="research")

    # 造出 agent 工作目录的临时件 + 项目交付物目录
    trig = paths.trigger_dir("research"); trig.mkdir(parents=True)
    resp = paths.response_dir("research"); resp.mkdir(parents=True)
    (trig / f"{iid}.request").write_text("{}", encoding="utf-8")
    (resp / f"{iid}.response").write_text("{}", encoding="utf-8")
    deliv = paths.deliverables_dir("pro_del")  # 自动建目录
    (deliv / "task_001_deliverable.md").write_text("# x", encoding="utf-8")

    summary = admin.delete_project("pro_del", store=store)

    assert summary["interactions"] == 1
    assert summary["files_removed"] == 2
    assert summary["project_dir_removed"] is True
    assert not (trig / f"{iid}.request").exists()
    assert not (resp / f"{iid}.response").exists()
    assert not paths.project_dir("pro_del").exists()
    assert store.get_project("pro_del") is None
    store.close()