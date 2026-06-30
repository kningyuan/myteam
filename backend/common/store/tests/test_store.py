#!/usr/bin/env python3
"""Phase 2 SQLite 真相库测试（D13）。

验证标准：状态可写可查；杀进程后能从库恢复；导出视图与库一致。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.store.store import Store  # noqa: E402


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
    store.upsert_task("pro_x", "task_001", name="调研", agent="research",
                      task_type="research", dependencies=[])
    store.set_task_status("pro_x", "task_001", "in_progress")
    t = store.get_task("pro_x", "task_001")
    assert t["status"] == "in_progress"
    assert t["started_at"] is not None
    store.set_task_status("pro_x", "task_001", "completed")
    t = store.get_task("pro_x", "task_001")
    assert t["status"] == "completed" and t["completed_at"] is not None


def test_list_projects(store):
    store.upsert_project("pro_a", title="A")
    store.upsert_project("pro_b", title="B")
    ids = {p["project_id"] for p in store.list_projects()}
    assert ids == {"pro_a", "pro_b"}


def test_interaction_and_events(store):
    store.upsert_project("pro_x")
    store.upsert_task("pro_x", "task_001")
    store.create_interaction("i1", "execute", "pro_x", task_id="task_001",
                             agent_id="research", task_status="in_progress")
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
    store.upsert_task("pro_x", "task_001", name="调研", agent="research",
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
            "id": "task_001", "name": "调研", "agent": "research",
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


def test_memory_delete(store):
    mid = store.memory_write("pro_x", "待删", "正文", tags=["tmp"])
    assert store.memory_get(mid) is not None
    assert store.memory_delete(mid) is True
    assert store.memory_get(mid) is None
    assert store.memory_delete(mid) is False


def test_list_all_conversations(store):
    store.create_conversation("channel/project-a", kind="project", project_id="pro_a", title="A")
    store.create_conversation("dm:research", kind="dm", title="Research DM")
    convs = store.list_all_conversations()
    ids = {c["conversation_id"] for c in convs}
    assert ids == {"channel/project-a", "dm:research"}
    dm = next(c for c in convs if c["conversation_id"] == "dm:research")
    assert dm["participants"] == []


def test_list_interactions_by_statuses(store):
    store.upsert_project("pro_x")
    store.create_interaction("i_pending", "execute", "pro_x", agent_id="a1")
    store.create_interaction("i_running", "execute", "pro_x", agent_id="a2")
    store.update_interaction("i_running", status="running")
    store.create_interaction("i_done", "execute", "pro_x", agent_id="a3")
    store.update_interaction("i_done", status="done")

    active = store.list_interactions_by_statuses(("pending", "running"))
    assert {r["interaction_id"] for r in active} == {"i_pending", "i_running"}

    done = store.list_interactions_by_statuses(("done",))
    assert {r["interaction_id"] for r in done} == {"i_done"}

    assert store.list_interactions_by_statuses(()) == []


def test_get_job(store):
    jid = store.create_job("pro_x", pid=12345)
    job = store.get_job(jid)
    assert job is not None
    assert job["job_id"] == jid
    assert job["project_id"] == "pro_x"
    assert store.get_job("nonexistent") is None


def test_delete_project_purges_all_tables_and_isolates(store):
    # 目标项目：含 task / interaction / run_event / memory + 合成 budget 事件
    store.upsert_project("pro_del", title="待删")
    store.upsert_task("pro_del", "task_001", name="t", agent="research")
    store.create_interaction("pro_del:task_001:execute:1", "execute", "pro_del",
                             task_id="task_001", agent_id="research")
    store.append_run_event("pro_del:task_001:execute:1", "step_start", {})
    store.append_run_event("pro_del:budget", "budget_over", {"used": 9})  # 合成 id（无交互行）
    store.memory_write("pro_del", "KB", "x", tags=["a"])
    # 另一个项目：必须不受影响
    store.upsert_project("pro_keep", title="保留")
    store.upsert_task("pro_keep", "task_001", name="k")
    store.append_run_event("pro_keep:task_001:execute:1", "step_start", {})

    inter = store.delete_project("pro_del")
    assert {"interaction_id": "pro_del:task_001:execute:1",
            "agent_id": "research"} in inter

    assert store.get_project("pro_del") is None
    assert store.list_tasks("pro_del") == []
    assert store.get_interaction("pro_del:task_001:execute:1") is None
    assert store.memory_search(project_id="pro_del") == []
    c = store._conn.execute(
        "SELECT COUNT(*) FROM run_event WHERE interaction_id LIKE 'pro_del:%'").fetchone()[0]
    assert c == 0
    # 隔离：另一个项目完好
    assert store.get_project("pro_keep") is not None
    assert store._conn.execute(
        "SELECT COUNT(*) FROM run_event WHERE interaction_id LIKE 'pro_keep:%'").fetchone()[0] == 1


def test_skill_review_does_not_overwrite_completed_task(store):
    """create_interaction 的 skill_review kind 不应回滚 task 终态。
    
    Regression test for Bug 3: skill_review daemon thread was calling
    create_interaction(..., task_status="in_progress") after _finalize_success
    already set task to "completed", overwriting the status.
    """
    store.upsert_project("p_skill", title="SkillReviewBug", status="in_progress")
    store.upsert_task("p_skill", "t1", name="test", agent="research")
    store.set_task_status("p_skill", "t1", "completed")
    assert store.get_task("p_skill", "t1")["status"] == "completed"
    store.create_interaction(
        "p_skill:t1:skill_review", "skill_review", "p_skill",
        task_id="t1", agent_id="research",
        task_status="in_progress",
    )
    assert store.get_task("p_skill", "t1")["status"] == "completed", \
        "skill_review should not overwrite task status to in_progress"
