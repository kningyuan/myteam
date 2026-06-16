#!/usr/bin/env python3
"""断点续跑与孤儿响应回收测试（D8）。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
from common.agent_port import AgentPort, WatchdogConfig, reconcile_on_start  # noqa: E402
from common.process import Process, ProcessConfig  # noqa: E402
from common.registry import get_spec  # noqa: E402
from common.run_kernel import resume_project  # noqa: E402
from common.store import Store  # noqa: E402
from common.submit_result import submit  # noqa: E402


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "state.db")
    cfg = WatchdogConfig(soft_idle_sec=5, hard_idle_sec=10, poll_interval=0.02, max_attempts=1)
    yield store, cfg
    store.close()


def _code_exec(iid: str, tid: str, project_id: str) -> dict:
    return {
        "interaction_id": iid, "kind": "execute", "status": "ok",
        "quality": {"score": 0.9, "known_gaps": [], "notes": "ok"},
        "result": {"outcome": {"kind": "artifact",
                               "artifact": {"path": f"{tid}/", "format": "code_project",
                                            "title": "hw"}}},
        "notes": "done",
    }


def test_resume_adopts_stuck_t1_and_continues(env, monkeypatch):
    """模拟内核线程中断：t1 响应在磁盘、interaction=running，resume 应结算 t1 并继续。"""
    store, wcfg = env
    pid = "proj_recover"
    store.upsert_project(pid, status="in_progress", meta={"goal": "g"})
    store.upsert_task(pid, "t1", name="写脚本", agent="developer", task_type="code-writing",
                      status="in_progress", dependencies=[])
    store.upsert_task(pid, "t2", name="测试", agent="tester", task_type="test-plan",
                      status="pending", dependencies=["t1"])

    iid = f"{pid}:t1:execute:1"
    store.create_interaction(iid, "execute", pid, task_id="t1", agent_id="developer")
    store.update_interaction(iid, status="running")

    proj_dir = paths.deliverables_dir(pid) / "t1"
    proj_dir.mkdir(parents=True)
    (proj_dir / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (proj_dir / "README.md").write_text("# 标题\n\n说明\n", encoding="utf-8")

    agent = "developer"
    trig = paths.trigger_dir(agent)
    resp_dir = paths.response_dir(agent)
    trig.mkdir(parents=True, exist_ok=True)
    resp_dir.mkdir(parents=True, exist_ok=True)
    (trig / f"{iid}.request").write_text("{}", encoding="utf-8")
    submit(_code_exec(iid, "t1", pid), resp_dir / f"{iid}.response")

    t2_done = {"done": False}

    def transport(ctx):
        req = ctx.request
        if req.task_id == "t2":
            spec = get_spec("test-plan")
            rel = "t2_deliverable.md"
            dv = paths.deliverables_dir(req.project_id) / rel
            content = "# 标题\n" + "".join(f"## {s}\n内容\n" for s in spec.required_sections)
            dv.write_text(content, encoding="utf-8")
            submit({
                "interaction_id": req.interaction_id, "kind": "execute", "status": "ok",
                "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
                "result": {"outcome": {"kind": "artifact",
                                         "artifact": {"path": rel, "title": "plan"}}},
            }, paths.response_dir(req.agent_id) / f"{req.interaction_id}.response")
            t2_done["done"] = True

    port = AgentPort(transport, store=store, config=wcfg)
    proc = Process(store, port, ProcessConfig())
    out = proc.resume(pid)

    assert store.get_interaction(iid)["status"] == "done"
    assert store.get_task(pid, "t1")["status"] in ("completed", "needs_review")
    assert t2_done["done"]
    assert out.status in ("completed", "partially_failed")


def test_kernel_order_reconcile_gc_then_resume_settles(env, monkeypatch):
    """run_kernel 顺序：reconcile → resume(settle) → gc，任务级回收不得断链。"""
    from common.agent_port import reconcile_on_start
    from common.workspace_gc import gc_workspace

    store, wcfg = env
    pid = "proj_kernel_ord"
    store.upsert_project(pid, status="in_progress", meta={"goal": "g"})
    store.upsert_task(pid, "t1", name="写脚本", agent="developer", task_type="code-writing",
                      status="in_progress", dependencies=[])

    iid = f"{pid}:t1:execute:1"
    store.create_interaction(iid, "execute", pid, task_id="t1", agent_id="developer")
    store.update_interaction(iid, status="timed_out")

    proj_dir = paths.deliverables_dir(pid) / "t1"
    proj_dir.mkdir(parents=True)
    (proj_dir / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (proj_dir / "README.md").write_text("# 标题\n\n说明\n", encoding="utf-8")

    agent = "developer"
    trig = paths.trigger_dir(agent)
    resp_dir = paths.response_dir(agent)
    trig.mkdir(parents=True, exist_ok=True)
    resp_dir.mkdir(parents=True, exist_ok=True)
    (trig / f"{iid}.request").write_text("{}", encoding="utf-8")
    submit(_code_exec(iid, "t1", pid), resp_dir / f"{iid}.response")

    reconcile_on_start(store)
    port = AgentPort(lambda ctx: None, store=store, config=wcfg)
    proc = Process(store, port, ProcessConfig())
    proc.resume(pid)
    gc_workspace(store)

    assert store.get_interaction(iid)["status"] == "done"
    assert store.get_task(pid, "t1")["status"] in ("completed", "needs_review")


def test_resume_adopts_timed_out_orphan(env, monkeypatch):
    """timed_out interaction + 合法磁盘响应 → resume 结算 t1，不误升不合规孤儿。"""
    store, wcfg = env
    pid = "proj_timed"
    store.upsert_project(pid, status="in_progress", meta={"goal": "g"})
    store.upsert_task(pid, "t1", name="写脚本", agent="developer", task_type="code-writing",
                      status="in_progress", dependencies=[])
    store.upsert_task(pid, "t2", name="测试", agent="tester", task_type="test-plan",
                      status="pending", dependencies=["t1"])

    iid = f"{pid}:t1:execute:1"
    store.create_interaction(iid, "execute", pid, task_id="t1", agent_id="developer")
    store.update_interaction(iid, status="timed_out")

    proj_dir = paths.deliverables_dir(pid) / "t1"
    proj_dir.mkdir(parents=True)
    (proj_dir / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (proj_dir / "README.md").write_text("# 标题\n\n说明\n", encoding="utf-8")

    agent = "developer"
    trig = paths.trigger_dir(agent)
    resp_dir = paths.response_dir(agent)
    trig.mkdir(parents=True, exist_ok=True)
    resp_dir.mkdir(parents=True, exist_ok=True)
    (trig / f"{iid}.request").write_text("{}", encoding="utf-8")
    submit(_code_exec(iid, "t1", pid), resp_dir / f"{iid}.response")

    port = AgentPort(lambda ctx: None, store=store, config=wcfg)
    proc = Process(store, port, ProcessConfig())
    out = proc.resume(pid)

    assert store.get_interaction(iid)["status"] == "done"
    assert store.get_task(pid, "t1")["status"] in ("completed", "needs_review")
    assert out.status in ("completed", "partially_failed")


def test_resume_keeps_timed_out_when_orphan_invalid(env):
    """不合规孤儿响应 → interaction 保持 timed_out，任务不完成。"""
    store, wcfg = env
    pid = "proj_invalid"
    store.upsert_project(pid, status="in_progress", meta={"goal": "g"})
    store.upsert_task(pid, "t1", name="写脚本", agent="developer", task_type="code-writing",
                      status="in_progress", dependencies=[])

    iid = f"{pid}:t1:execute:1"
    store.create_interaction(iid, "execute", pid, task_id="t1", agent_id="developer")
    store.update_interaction(iid, status="timed_out")

    agent = "developer"
    resp_dir = paths.response_dir(agent)
    resp_dir.mkdir(parents=True, exist_ok=True)
    # interaction_id 不匹配 → 不可采纳
    (resp_dir / f"{iid}.response").write_text(
        json.dumps({"interaction_id": "OTHER", "kind": "execute", "status": "ok"}),
        encoding="utf-8",
    )

    port = AgentPort(lambda ctx: None, store=store, config=wcfg)
    proc = Process(store, port, ProcessConfig())
    proc.resume(pid)

    # 不合规孤儿不会被采纳；续跑重派后端口 no_response → failed，任务不得误升 completed
    assert store.get_interaction(iid)["status"] in ("timed_out", "failed")
    assert store.get_task(pid, "t1")["status"] not in ("completed", "needs_review")


def test_maybe_extract_skills_writes_draft(env, tmp_path, monkeypatch):
    """项目 completed + skill_extract_enabled → auto SKILL.md 草案。"""
    store, wcfg = env
    monkeypatch.setattr("common.skill_extract.MYTEAM_ROOT", tmp_path)
    monkeypatch.setattr("common.skill_extract.SKILLS_DIR", tmp_path / "business/skills")

    pid = "self-upgrade"
    store.upsert_project(pid, status="in_progress")
    store.upsert_task(
        pid, "skill-extract", agent="product", task_type="research",
        status="completed", dependencies=[],
    )
    dv = paths.deliverables_dir(pid) / "skill-extract_deliverable.md"
    dv.parent.mkdir(parents=True, exist_ok=True)
    dv.write_text("# 草案\n\n" + "pattern " * 30, encoding="utf-8")
    store.update_task_meta(pid, "skill-extract", ref="skill-extract_deliverable.md")

    port = AgentPort(lambda ctx: None, store=store, config=wcfg)
    proc = Process(store, port, ProcessConfig(skill_extract_enabled=True))
    proc._maybe_extract_skills(pid)

    draft = tmp_path / "business/skills/auto-self-upgrade-skill-extract/SKILL.md"
    assert draft.is_file()
    assert "skill-extract" in draft.read_text(encoding="utf-8")


def test_resume_unblocks_when_upstream_recovers(env, monkeypatch):
    """上游 failed→needs_review 后，resume 应解除下游 blocked 并调度。"""
    store, wcfg = env
    pid = "pro_unblock"
    store.upsert_project(pid, status="in_progress", meta={"goal": "g"})
    store.upsert_task(pid, "t1", name="调研", agent="research", task_type="research",
                      status="needs_review", dependencies=[])
    store.upsert_task(pid, "t2", name="汇总", agent="main", task_type="strategy",
                      status="blocked", dependencies=["t1"])

    from common.registry import get_spec
    from common.tests.test_process import GOOD_Q, _port, _write_exec, valid_content

    def transport(ctx):
        ctx.emit("step_start")
        _write_exec(ctx, valid_content("strategy"), GOOD_Q)

    proc = Process(store, _port(store, wcfg, transport), ProcessConfig())
    out = proc.resume(pid)
    assert out.tasks["t2"].status in ("completed", "needs_review")
    assert store.get_task(pid, "t2")["status"] in ("completed", "needs_review")


def test_resume_merges_workflow_description(env, monkeypatch, tmp_path):
    """resume 应从 workflow 补全 store 中缺失的 task description（intent 来源）。"""
    store, wcfg = env
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir()
    (wf_dir / "merge-desc.yaml").write_text(
        """id: merge-desc
version: "1.0"
description: test
tasks:
  - id: t-arch
    name: 架构调研
    agent: arch
    task_type: architecture-review
    dependencies: []
    description: |
      【对象】目标系统架构
      【任务】架构调研，禁止全仓扫源码
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("common.workflow_loader.workflows_dir", lambda: wf_dir)
    pid = "merge-desc-proj"
    store.upsert_project(pid, status="in_progress", meta={"workflow": "merge-desc"})
    store.upsert_task(pid, "t-arch", name="架构调研", agent="arch",
                      task_type="architecture-review", status="failed")
    port = AgentPort(lambda ctx: None, store=store, config=wcfg)
    proc = Process(store, port, ProcessConfig())
    tasks = proc._merge_workflow_descriptions("merge-desc", proc._tasks_from_store(pid))
    t = next(t for t in tasks if t["id"] == "t-arch")
    assert "架构" in t["description"]
    assert "禁止全仓扫源码" in t["description"]
