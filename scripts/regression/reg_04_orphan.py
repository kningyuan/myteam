#!/usr/bin/env python3
"""REG-04：孤儿回收 E2E（脚本化，不需要真实 CLI）。

测试路径：
  timed_out interaction + 合法 .response → reconcile_on_start → proc.resume → task needs_review/completed
  timed_out interaction + 不合规 .response → 保持 failed

K4 = 回收成功数 / 孤儿总数（本次 run），阈值 ≥ 95%。

退出码：0=PASS，1=FAIL
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# 插入 backend 到 sys.path
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "backend"))

import common.paths as paths  # noqa: E402
from common.agent_port import WatchdogConfig, reconcile_on_start  # noqa: E402
from common.process import Process, ProcessConfig  # noqa: E402
from common.store import Store  # noqa: E402
from common.submit_result import submit  # noqa: E402


def _valid_response(iid: str, tid: str) -> dict:
    """合规的 execute 响应（code-writing 任务类型，指向 code_project 目录）。"""
    return {
        "interaction_id": iid,
        "kind": "execute",
        "status": "ok",
        "quality": {"score": 0.9, "known_gaps": [], "notes": "ok"},
        "result": {"outcome": {"kind": "artifact",
                               "artifact": {"path": f"{tid}/", "format": "code_project",
                                            "title": "hw"}}},
        "notes": "done",
    }


def _setup_code_project(deliverables_dir: Path, tid: str) -> None:
    """写最小合规代码工程目录（Gate check_code_project 需要 ≥1 代码文件）。"""
    proj = deliverables_dir / tid
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (proj / "README.md").write_text("# 标题\n\n说明\n", encoding="utf-8")


def run_positive_case(tmp: Path) -> dict:
    """正向：timed_out + 合法 .response → 采纳，task = needs_review/completed。"""
    store = Store(tmp / "state_pos.db")
    pid = "reg-04-orphan-pos"
    tid = "t1"
    agent = "developer"

    store.upsert_project(pid, status="in_progress", meta={"goal": "reg04 positive"})
    store.upsert_task(pid, tid, name="代码任务", agent=agent, task_type="code-writing",
                      status="in_progress", dependencies=[])

    iid = f"{pid}:{tid}:execute:1"
    store.create_interaction(iid, "execute", pid, task_id=tid, agent_id=agent)
    store.update_interaction(iid, status="timed_out")

    # 写代码工程目录（Gate 需要文件存在）
    deliverables = paths.deliverables_dir(pid)
    _setup_code_project(deliverables, tid)

    # 写 .request + 合规 .response
    trig = paths.trigger_dir(agent)
    resp_dir = paths.response_dir(agent)
    trig.mkdir(parents=True, exist_ok=True)
    resp_dir.mkdir(parents=True, exist_ok=True)
    (trig / f"{iid}.request").write_text("{}", encoding="utf-8")
    submit(_valid_response(iid, tid), resp_dir / f"{iid}.response")

    # Step 1: reconcile_on_start
    rec = reconcile_on_start(store)

    interaction_after_reconcile = store.get_interaction(iid)
    reconcile_adopted = rec.get("adopted", 0)

    # Step 2: proc.resume → settle_in_progress_task → Gate → task done
    wcfg = WatchdogConfig(soft_idle_sec=5, hard_idle_sec=10, poll_interval=0.02, max_attempts=1)
    from common.agent_port import AgentPort
    port = AgentPort(lambda ctx: None, store=store, config=wcfg)
    proc = Process(store, port, ProcessConfig())
    proc.resume(pid)

    task_final = store.get_task(pid, tid)
    interaction_final = store.get_interaction(iid)
    store.close()

    passed = task_final["status"] in ("completed", "needs_review")
    return {
        "case": "positive",
        "reconcile_adopted": reconcile_adopted,
        "interaction_after_reconcile": interaction_after_reconcile["status"],
        "interaction_final": interaction_final["status"],
        "task_final": task_final["status"],
        "passed": passed,
    }


def run_negative_case(tmp: Path) -> dict:
    """负向：timed_out + 不合规 .response（interaction_id 不匹配）→ 保持 failed。"""
    store = Store(tmp / "state_neg.db")
    pid = "reg-04-orphan-neg"
    tid = "t1"
    agent = "developer"

    store.upsert_project(pid, status="in_progress", meta={"goal": "reg04 negative"})
    store.upsert_task(pid, tid, name="代码任务", agent=agent, task_type="code-writing",
                      status="in_progress", dependencies=[])

    iid = f"{pid}:{tid}:execute:1"
    store.create_interaction(iid, "execute", pid, task_id=tid, agent_id=agent)
    store.update_interaction(iid, status="timed_out")

    # 写不合规响应（interaction_id 不匹配）
    resp_dir = paths.response_dir(agent)
    resp_dir.mkdir(parents=True, exist_ok=True)
    bad = _valid_response("WRONG_ID", tid)
    bad["interaction_id"] = "WRONG_ID"
    (resp_dir / f"{iid}.response").write_text(json.dumps(bad), encoding="utf-8")

    # Step 1: reconcile_on_start → 不应采纳
    rec = reconcile_on_start(store)
    reconcile_adopted = rec.get("adopted", 0)

    # Step 2: proc.resume → settle 找不到合规响应 → run_task → no_response → failed
    wcfg = WatchdogConfig(soft_idle_sec=1, hard_idle_sec=2, poll_interval=0.02, max_attempts=1)
    from common.agent_port import AgentPort
    port = AgentPort(lambda ctx: None, store=store, config=wcfg)
    proc = Process(store, port, ProcessConfig())
    proc.resume(pid)

    task_final = store.get_task(pid, tid)
    store.close()

    # 负例：task 不应为 completed/needs_review
    task_not_completed = task_final["status"] not in ("completed", "needs_review")
    return {
        "case": "negative",
        "reconcile_adopted": reconcile_adopted,
        "task_final": task_final["status"],
        "passed": task_not_completed,
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="reg04_") as tmp_str:
        tmp = Path(tmp_str)

        # 重定向 paths 到 tmp（同测试框架的 monkeypatch 模式，但这里直接改模块属性）
        original_workspaces = paths.WORKSPACES_DIR
        original_projects = paths.PROJECTS_DIR
        paths.WORKSPACES_DIR = tmp / "workspaces"
        paths.PROJECTS_DIR = tmp / "project"

        try:
            print("--- REG-04 正向用例 ---")
            pos = run_positive_case(tmp)
            print(f"  reconcile_adopted: {pos['reconcile_adopted']}")
            print(f"  interaction after reconcile: {pos['interaction_after_reconcile']}")
            print(f"  interaction final: {pos['interaction_final']}")
            print(f"  task final: {pos['task_final']}")
            print(f"  结果: {'PASS' if pos['passed'] else 'FAIL'}")

            print("")
            print("--- REG-04 负向用例 ---")
            neg = run_negative_case(tmp)
            print(f"  reconcile_adopted: {neg['reconcile_adopted']}")
            print(f"  task final: {neg['task_final']}")
            print(f"  结果: {'PASS' if neg['passed'] else 'FAIL'}")

        finally:
            paths.WORKSPACES_DIR = original_workspaces
            paths.PROJECTS_DIR = original_projects

    # K4 = 正向采纳数 / 孤儿总数（1 个孤儿测试）
    k4_adopted = 1 if pos["passed"] else 0
    k4_total = 1
    k4 = k4_adopted / k4_total

    print("")
    print("=== REG-04 结果 ===")
    overall = pos["passed"] and neg["passed"]
    print(f"正向: {'PASS' if pos['passed'] else 'FAIL'}")
    print(f"负向: {'PASS' if neg['passed'] else 'FAIL'}")
    print(f"K4:   {k4_adopted}/{k4_total} = {k4*100:.1f}% (阈值 ≥95%)")
    print(f"K4 通过: {'YES' if k4 >= 0.95 else 'NO'}")
    print(f"REG-04: {'PASS' if overall else 'FAIL'}")

    sys.path.insert(0, str(_REPO_ROOT / "scripts" / "regression"))
    from regression_archive import append_run_record  # noqa: E402

    rec = append_run_record(
        reg_id="REG-04",
        project_id="reg-04-orphan-pos",
        pass_=overall,
        kpis={"K4": k4, "positive": pos["passed"], "negative": neg["passed"]},
        meta={"mode": "scripted", "note": "tmp db; artifact may be empty"},
    )
    print(f"  I-06 archived: run_id={rec['run_id']}")

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
