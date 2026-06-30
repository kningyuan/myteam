#!/usr/bin/env python3
"""子模块协作联动测试：project → process。

验证协作链路：
  1. JobSupervisor.start_job 启动后台线程跑 Process.run；job 状态随 Process 终态更新
     （project_runtime / job_supervisor → process 协作）
  2. Process.run 把项目状态写入 Store；JobSupervisor.get_job 能查到同一 job 的终态
  3. project_admin.delete_project 删除项目时，Store 行 + 项目交付物目录一并清理
     （project_admin → store + 文件系统协作）

参考 test_integration.py 的 FakeOpencode 模式与 env fixture。
"""
import json
import sys
import time
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
import common.agent.agent_registry as agent_registry_mod  # noqa: E402
from common.agent.agent_port import AgentPort, WatchdogConfig  # noqa: E402
from common.agent.agent_transport import AdapterTransport  # noqa: E402
from common.gate.registry import get_spec  # noqa: E402
from common.delivery.submit_result import submit  # noqa: E402
from common.process.process import Process, ProcessConfig  # noqa: E402
from common.project.job_supervisor import JobSupervisor  # noqa: E402
from common.project.project_admin import delete_project  # noqa: E402
from common.store.store import Store  # noqa: E402


class FakeEvent:
    def __init__(self, kind, data=None):
        self.kind = types.SimpleNamespace(value=kind)
        self.data = data or {}


class FakeOpencode:
    """模拟 opencode：按提示词产出合规交付物 + 经 submit_result 写回。"""

    def run(self, request):
        yield FakeEvent("step_start")
        yield FakeEvent("text", {"chunk": "working..."})
        msg = request.message
        dv_abs = _line_after(msg, "写入文件：")
        resp_path = _line_after(msg, "--out ").split(" --file")[0]
        iid = Path(resp_path).stem
        task_type = "research"
        spec = get_spec(task_type)
        content = ["# 标题\n"]
        for s in spec.required_sections:
            content.append(f"## {s}\n「{s}」的足够具体内容，覆盖要点与细节说明充分。\n")
        Path(dv_abs).parent.mkdir(parents=True, exist_ok=True)
        Path(dv_abs).write_text("\n".join(content), encoding="utf-8")
        rel = Path(dv_abs).name
        submit({
            "interaction_id": iid, "kind": "execute", "status": "ok",
            "notes": f"完成 {iid} 的调研。",
            "quality": {"score": 0.9, "known_gaps": [], "notes": "自评良好"},
            "result": {"outcome": {"kind": "artifact",
                                   "artifact": {"path": rel, "title": "调研"}}},
        }, Path(resp_path))
        yield FakeEvent("step_finish", {"tokens": 500})


def _line_after(s, marker):
    i = s.index(marker) + len(marker)
    return s[i:s.index("\n", i)].strip()


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """隔离 workspaces / projects / registry，避免污染工程。"""
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    (tmp_path / "workspaces" / "workspace-research").mkdir(parents=True)
    reg_path = tmp_path / "agents_registry.json"
    reg_path.write_text(json.dumps({
        "version": "2.0",
        "agents": {
            "research": {"name": "调研", "task_types": ["research"]},
        },
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(agent_registry_mod, "REGISTRY_FILE", reg_path)

    store = Store(tmp_path / "state.db")
    wcfg = WatchdogConfig(soft_idle_sec=5, hard_idle_sec=10, poll_interval=0.02, max_attempts=1)
    yield store, wcfg
    store.close()


def _build_process(store, wcfg) -> Process:
    """构造一个用 FakeOpencode 的 Process（不依赖真实 CLI）。"""
    transport = AdapterTransport(
        adapter=FakeOpencode(),
        agents_config={"research": {"model": "m1"}},
        request_factory=lambda **kw: types.SimpleNamespace(**kw),
    )
    port = AgentPort(transport, store=store, config=wcfg)
    return Process(store, port, ProcessConfig(token_budget=10000))


def _wait_job_done(supervisor: JobSupervisor, project_id: str, timeout: float = 30.0) -> None:
    """轮询等待 job 结束（FakeOpencode 同步，应很快完成）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not supervisor.is_running(project_id):
            return
        time.sleep(0.05)
    raise AssertionError(f"job for {project_id} 未在 {timeout}s 内结束")


def test_job_supervisor_runs_process_and_records_terminal_status(env):
    """JobSupervisor 启动后台线程跑 Process.run；job 与项目状态都到终态。"""
    store, wcfg = env
    proc = _build_process(store, wcfg)
    project_id = "pro_pp_job"
    tasks = [
        {"id": "t1", "agent": "research", "task_type": "research", "dependencies": []},
    ]
    outcomes: dict = {}

    def runner() -> None:
        outcomes["o"] = proc.run(
            project_id, title="project→process", goal="协作联动",
            agents=["research"], tasks=tasks,
        )

    # 1) JobSupervisor 接管 Process.run（project → process 协作入口）
    supervisor = JobSupervisor(store)
    job_id = supervisor.start_job(project_id, runner)
    assert job_id
    _wait_job_done(supervisor, project_id)

    # 2) Process 跑完，项目状态写入 Store（Process → Store）
    assert outcomes["o"].status == "completed"
    proj = store.get_project(project_id)
    assert proj and proj["status"] == "completed"

    # 3) JobSupervisor 把 job 状态更新为 completed（JobSupervisor → Store 同一真相源）
    job = supervisor.get_job(project_id)
    assert job and job["status"] == "completed"
    assert job["job_id"] == job_id

    # 4) 交付物真实落盘（Process 用 worker prompt 跑出来的）
    dv = paths.deliverables_dir(project_id) / "t1_deliverable.md"
    assert dv.exists() and "调研背景" in dv.read_text(encoding="utf-8")


def test_delete_project_clears_store_rows_and_deliverables(env):
    """project_admin.delete_project 删除项目：DB 行 + 交付物目录一并清理。"""
    store, wcfg = env
    proc = _build_process(store, wcfg)
    project_id = "pro_pp_del"
    proc.run(
        project_id, title="待删除项目", goal="删除联动",
        agents=["research"],
        tasks=[{"id": "t1", "agent": "research", "task_type": "research", "dependencies": []}],
    )
    # 前置：项目与交付物存在
    assert store.get_project(project_id) is not None
    dv_dir = paths.deliverables_dir(project_id)
    assert (dv_dir / "t1_deliverable.md").exists()

    # 1) delete_project 返回清理摘要（project_admin → store + 文件系统协作）
    summary = delete_project(project_id, store=store)
    assert summary["interactions"] >= 1          # 至少删了 t1 的 interaction
    assert summary["project_dir_removed"] is True

    # 2) Store 中项目行消失
    assert store.get_project(project_id) is None
    # 该项目的 task 行也清掉
    assert store.list_tasks(project_id) == []

    # 3) 项目交付物目录被物理删除
    pdir = paths.project_dir(project_id)
    assert not pdir.exists()
    assert not dv_dir.exists()

    # 4) 重复删除幂等：不抛异常，摘要为空清理
    again = delete_project(project_id, store=store)
    assert again["interactions"] == 0
    assert again["project_dir_removed"] is False
