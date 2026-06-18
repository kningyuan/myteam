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


def test_list_library(client):
    r = client.get("/api/skills/library")
    assert r.status_code == 200
    body = r.json()
    assert "skills" in body
    assert "count" in body
    assert body["count"] == len(body["skills"])
    if body["skills"]:
        assert "id" in body["skills"][0]
        assert "name" in body["skills"][0]
        assert "is_mountable" in body["skills"][0]


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


def test_delete_library_skill(tmp_path, monkeypatch):
    import shutil

    skills_dir = tmp_path / "business" / "skills"
    skill_id = "tmp-delete-me"
    skill_dir = skills_dir / skill_id
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: x\n---\n# x\n", encoding="utf-8")

    monkeypatch.setattr("common.skill_catalog.SKILLS_DIR", skills_dir)
    monkeypatch.setattr("common.skill_catalog.MYTEAM_ROOT", tmp_path)
    monkeypatch.setattr("common.skill_extract.SKILLS_DIR", skills_dir)
    monkeypatch.setattr("common.skill_link.SKILLS_DIR", skills_dir)

    app = FastAPI()
    app.include_router(skills_api.router)
    c = TestClient(app)

    r = c.delete(f"/api/skills/library/{skill_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["skill_id"] == skill_id
    assert not skill_dir.exists()

    assert c.delete(f"/api/skills/library/{skill_id}").status_code == 404


def test_delete_library_rejects_missing(client):
    assert client.delete("/api/skills/library/does-not-exist-xyz").status_code == 404
