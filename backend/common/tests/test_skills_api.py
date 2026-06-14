#!/usr/bin/env python3
"""skills_api 路由测试。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "backend"))

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from hub.api import skills_api  # noqa: E402


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(skills_api.router)
    return TestClient(app)


def test_list_drafts(client):
    r = client.get("/api/skills/drafts")
    assert r.status_code == 200
    body = r.json()
    assert "drafts" in body
    assert "count" in body


def test_matrix_audit(client):
    r = client.get("/api/skills/matrix")
    assert r.status_code == 200
    body = r.json()
    assert "registered_task_types" in body


def test_draft_404(client):
    assert client.get("/api/skills/drafts/auto-nonexistent-xyz/diff").status_code == 404
