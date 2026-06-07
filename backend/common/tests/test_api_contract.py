#!/usr/bin/env python3
"""前后端接口契约形状测试 —— 防「代码 / 契约(api-reference.md) / 前端」三方漂移回归。

对前端实际消费的关键端点，断言响应必含字段；字段被删/改名即 CI 红。
对应《docs/接口一致性整改方案.md》§4.4，与 D13/D17 测试同域。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "backend"))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from common.store import Store  # noqa: E402


# ── A：项目总览全集（含 title） ─────────────────────────────
# 用全集断言（== 而非 in）落实 §4.5：改前端消费字段须先改契约 + 测试。
# 增删字段都会让此用例变红，强制走「变更登记」流程。
OVERVIEW_KEYS = {"project_id", "title", "status", "mode", "task_counts",
                 "progress", "tokens", "budget", "budget_ratio", "budget_state", "tasks"}


def test_overview_full_shape(tmp_path):
    from common.observability import project_overview
    store = Store(tmp_path / "state.db")
    store.upsert_project("p1", title="调研报告", status="in_progress")
    ov = project_overview(store, "p1")
    store.close()
    assert set(ov.keys()) == OVERVIEW_KEYS
    assert ov["title"] == "调研报告"          # fix A：不再退化成 project_id


def test_overview_title_falls_back_to_pid(tmp_path):
    from common.observability import project_overview
    store = Store(tmp_path / "state.db")
    ov = project_overview(store, "ghost")     # 项目行缺失 → proj 兜底
    store.close()
    assert ov["title"] == "ghost"             # 与前端 ov.title || id 行为一致，无副作用


# ── C：群列表含 last_message_at（与 search_groups 对齐） ────
def test_groups_list_has_last_message_at(monkeypatch):
    from base import group_manager
    monkeypatch.setattr(group_manager, "_load_groups", lambda: {
        "g1": {"id": "g1", "name": "组", "members": ["a"], "status": "active",
               "messages": [{"timestamp": 100}, {"timestamp": 250}], "created_at": 50},
    })
    groups = group_manager.list_groups()
    assert groups and "last_message_at" in groups[0]
    assert groups[0]["last_message_at"] == 250    # = max(messages.timestamp)


# ── 摘要 totals 形状（Home 仪表盘） ────────────────────────
def test_summary_totals_shape(tmp_path):
    from common.observability import projects_summary
    store = Store(tmp_path / "state.db")
    store.upsert_project("p1", title="x", status="in_progress")
    summary = projects_summary(store)
    store.close()
    assert {"projects", "running", "tokens"} <= summary["totals"].keys()


# ── E：错误信封含 error.message（落实 api-reference.md 附录 B） ──
def test_http_exception_envelope_has_message():
    from hub.api.server import http_exception_envelope
    app = FastAPI()
    app.add_exception_handler(HTTPException, http_exception_envelope)

    @app.get("/boom")
    def boom():
        raise HTTPException(status_code=409, detail="项目运行中，请先取消再删除")

    r = TestClient(app).get("/boom")
    assert r.status_code == 409
    body = r.json()
    assert body["error"]["message"] == "项目运行中，请先取消再删除"   # 前端 apiErr 读这里
    assert body["detail"] == "项目运行中，请先取消再删除"             # 向后兼容：仍可读 detail


def test_real_app_mro_envelope_vs_default_404():
    """在真实 app（srv.app）上锁死 E 设计赖以成立的 MRO 优先级——防有人改 import 后静默回归：
    - 手抛 fastapi.HTTPException(409) → envelope handler 接管，产 error 信封；
    - 未匹配路由的 Starlette 404（父类异常，不命中 fastapi.HTTPException）→ 仍走默认裸 {detail}。
    上面的 test_http_exception_envelope 只在全新 app 上验了 handler 自身，没验真实 app 的优先级。"""
    import hub.api.server as srv
    client = TestClient(srv.app)

    # (a) 不存在的路由 → Starlette HTTPException(404)，不被 envelope handler 误吞
    r404 = client.get("/api/__definitely_not_a_route__")
    assert r404.status_code == 404
    assert "error" not in r404.json()        # 关键：保持默认裸 detail 形状

    # (b) 手抛 fastapi.HTTPException(409) → envelope handler 归一化
    pid = "ui_contract_mro_probe"
    srv._KERNEL_RUNS[pid] = {"running": True, "error": None}
    try:
        r409 = client.post("/api/projects/run", json={"goal": "x", "project_id": pid})
        assert r409.status_code == 409
        assert r409.json()["error"]["message"] == "该项目正在运行"   # 信封
        assert r409.json()["detail"] == "该项目正在运行"              # 向后兼容
    finally:
        srv._KERNEL_RUNS.pop(pid, None)


# ── D：run-status 反映自动续跑 ─────────────────────────────
def test_resume_marks_run_status(tmp_path, monkeypatch):
    """D-fast：续跑进行时 on_start 标记 running=true、收尾 on_end 清除——与 server.py
    _mark_run/_clear_run 注入逻辑一致，堵住「启动续跑 vs 用户点击」并发再续跑窗口。"""
    from common import run_kernel
    store = Store(tmp_path / "state.db")
    store.upsert_project("p1", title="R", status="in_progress")

    runs: dict = {}
    seen: dict = {}

    def mark(pid):
        runs[pid] = {"running": True, "error": None}

    def clear(pid, err):
        runs[pid] = {"running": False, "error": str(err) if err else None}

    def fake_resume(pid, **kw):
        seen["running_during"] = runs.get(pid, {}).get("running")   # 续跑进行时读到的标记

    monkeypatch.setattr(run_kernel, "resume_project", fake_resume)
    monkeypatch.setattr(run_kernel, "reconcile_on_start", lambda s: None)
    monkeypatch.setattr(run_kernel, "gc_workspace", lambda s: None)

    resumed = run_kernel.resume_in_progress_projects(store=store, on_start=mark, on_end=clear)
    store.close()
    assert resumed == ["p1"]
    assert seen["running_during"] is True         # 续跑期 run-status 报 running:true
    assert runs["p1"]["running"] is False          # 收尾清除
