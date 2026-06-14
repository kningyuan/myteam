#!/usr/bin/env python3
"""P1 E2E baseline — fast platform smoke without real CLI.

Covers: Hub health, Store roundtrip + tokens_total, roundtable parse, kernel_run meta.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "backend"))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from common.store import Store  # noqa: E402


@pytest.fixture()
def client():
    import hub.api.server as srv

    return TestClient(srv.app)


def test_hub_health_endpoint_returns_200(client):
    """Test 1: Hub app boots; GET /api/status returns 200."""
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert "project_count" in body


def test_store_roundtrip_tokens_total(tmp_path):
    """Test 2: project/task/interaction roundtrip; tokens_total sums interactions."""
    db = tmp_path / "state.db"
    store = Store(db)
    store.upsert_project("p_e2e", title="E2E Baseline", status="in_progress")
    store.upsert_task(
        "p_e2e", "t1", name="Smoke task", agent="developer",
        task_type="code-deliverable", status="pending",
    )
    store.create_interaction(
        "p_e2e:t1:1", "agent_run", "p_e2e",
        task_id="t1", agent_id="developer", backend="opencode",
    )
    store.update_interaction("p_e2e:t1:1", status="done", tokens=120)
    store.create_interaction(
        "p_e2e:t1:2", "agent_run", "p_e2e",
        task_id="t1", agent_id="developer", backend="opencode",
    )
    store.bump_interaction_tokens("p_e2e:t1:2", 80)

    assert store.get_project("p_e2e")["title"] == "E2E Baseline"
    assert store.get_task("p_e2e", "t1")["agent"] == "developer"
    assert store.get_interaction("p_e2e:t1:1")["tokens"] == 120
    assert store.get_interaction("p_e2e:t1:2")["tokens"] == 80
    assert store.tokens_total("p_e2e") == 200
    store.close()


def test_roundtable_extract_correction_items():
    """Test 3: parse correction items from Workflow v3 sample draft."""
    from common.roundtable_runtime import extract_correction_items

    draft = """
## 推荐做法（本题最佳实践）

#### 修正项 1：E2E 测试基线提前至 P1 末尾（三角色一致）
- P1 末尾必须产出至少 1 条编排内核完整链路的 E2E 测试
- Gate：测试通过率 100%

#### 修正项 2：token 验收改功能性标准（三角色一致）
- adapter 能提取 + API 能返回 + 前端能展示

#### 修正项 7：Gate 条件量化参照 FRAMEWORK-FREEZE.md 标准
- P4 Gate：逐项列出验收清单
"""
    items = extract_correction_items(draft)
    assert [n for n, _, _ in items] == [1, 2, 7]
    assert "E2E" in items[0][1]
    assert "token" in items[1][1].lower()
    assert "Gate 条件量化" in items[2][1]


def test_kernel_run_meta_get_set(tmp_path, monkeypatch):
    """Test 4: hub_kernel_run persisted in project.meta; _get_kernel_run reads it."""
    import common.store as cstore
    from hub.services import kernel_run

    db = tmp_path / "state.db"
    orig = cstore.Store
    monkeypatch.setattr(cstore, "Store", lambda *a, **k: orig(db))

    store = cstore.Store()
    store.upsert_project("p_kernel", title="K", status="in_progress")
    store.close()

    kernel_run._set_kernel_run("p_kernel", running=True, error=None)

    got = kernel_run._get_kernel_run("p_kernel")
    assert got["running"] is True
    assert got.get("error") is None

    store2 = cstore.Store()
    meta = (store2.get_project("p_kernel") or {}).get("meta") or {}
    store2.close()
    assert meta.get("hub_kernel_run", {}).get("running") is True

    kernel_run._clear_kernel_run("p_kernel")
    got2 = kernel_run._get_kernel_run("p_kernel")
    assert got2["running"] is False
