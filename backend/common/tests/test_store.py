#!/usr/bin/env python3
"""Phase 2 SQLite 真相库测试（D13）。

验证标准：状态可写可查；杀进程后能从库恢复；导出视图与库一致。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.store import Store  # noqa: E402


@pytest.fixture()
def store(tmp_path):
    s = Store(tmp_path / "state.db")
    yield s
    s.close()


def test_schema_idempotent(tmp_path):
    db = tmp_path / "x.db"
    Store(db).close()
    Store(db).close()  # 第二次打开不应报错（CREATE IF NOT EXISTS）


def test_project_and_task_crud(store):
    store.upsert_project("pro_x", title="GEO", mode="recurring")
    store.upsert_task("pro_x", "task_001", name="调研", agent="researcher",
                      task_type="research", dependencies=[])
    store.set_task_status("pro_x", "task_001", "in_progress")
    t = store.get_task("pro_x", "task_001")
    assert t["status"] == "in_progress"
    assert t["started_at"] is not None
    store.set_task_status("pro_x", "task_001", "completed")
    t = store.get_task("pro_x", "task_001")
    assert t["status"] == "completed" and t["completed_at"] is not None


def test_interaction_and_events(store):
    store.upsert_project("pro_x")
    store.upsert_task("pro_x", "task_001")
    store.create_interaction("i1", "execute", "pro_x", task_id="task_001",
                             agent_id="researcher", task_status="in_progress")
    assert store.get_task("pro_x", "task_001")["status"] == "in_progress"
    s1 = store.append_run_event("i1", "step_start")
    s2 = store.append_run_event("i1", "text", {"chunk": "hi"})
    assert (s1, s2) == (1, 2)
    store.update_interaction("i1", status="done", response_ref="x.response", tokens=120)
    store.update_interaction("i1", tokens=30)
    inter = store.get_interaction("i1")
    assert inter["status"] == "done"
    assert inter["tokens"] == 150
    assert inter["last_event_at"] is not None
    assert len(store.list_run_events("i1")) == 2


def test_idempotent_recreate_interaction(store):
    store.upsert_project("pro_x")
    store.create_interaction("i1", "execute", "pro_x", attempt=1)
    store.create_interaction("i1", "execute", "pro_x", attempt=2)  # 重投递
    inter = store.get_interaction("i1")
    assert inter["attempt"] == 2 and inter["status"] == "pending"


def test_export_view_matches_db(store):
    store.upsert_project("pro_x", title="GEO")
    store.upsert_task("pro_x", "task_001", name="调研", agent="researcher",
                      task_type="research", dependencies=[])
    store.upsert_task("pro_x", "sub_001", name="子调研", parent_id="task_001",
                      dependencies=[])
    store.set_task_status("pro_x", "task_001", "completed")
    view = store.export_project("pro_x")
    assert view["project"]["title"] == "GEO"
    assert len(view["tasks"]) == 1  # 子任务嵌套，不出现在顶层
    top = view["tasks"][0]
    assert top["id"] == "task_001" and top["status"] == "completed"
    assert len(top["subtasks"]) == 1 and top["subtasks"][0]["id"] == "sub_001"


def test_recover_after_reopen(tmp_path):
    db = tmp_path / "state.db"
    s1 = Store(db)
    s1.upsert_project("pro_x")
    s1.upsert_task("pro_x", "task_001", name="t")
    s1.create_interaction("i1", "execute", "pro_x", task_id="task_001")
    s1.update_interaction("i1", status="running", touch_event=True)
    s1.close()  # 模拟进程退出
    s2 = Store(db)  # 重启恢复
    assert s2.get_interaction("i1")["status"] == "running"
    assert s2.get_task("pro_x", "task_001")["name"] == "t"
    s2.close()


def test_import_task_data_roundtrip(store):
    data = {
        "project": {"title": "GEO", "mode": "one_shot", "status": "in_progress"},
        "tasks": [{
            "id": "task_001", "name": "调研", "agent": "researcher",
            "task_type": "research", "status": "completed", "dependencies": [],
            "subtasks": [{"id": "sub_001", "name": "子", "status": "completed",
                          "dependencies": []}],
        }],
    }
    counts = store.import_task_data("pro_x", data)
    assert counts == {"tasks": 1, "subtasks": 1}
    view = store.export_project("pro_x")
    assert view["tasks"][0]["id"] == "task_001"
    assert view["tasks"][0]["subtasks"][0]["id"] == "sub_001"


def test_memory_write_search(store):
    mid = store.memory_write("pro_x", "GEO 结论", "结构化数据是关键", tags=["geo", "seo"])
    assert store.memory_get(mid)["title"] == "GEO 结论"
    assert store.memory_search(tags=["geo"])
    assert store.memory_search(text="结构化")
    assert not store.memory_search(tags=["nope"])
