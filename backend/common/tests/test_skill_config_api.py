#!/usr/bin/env python3
"""R-C9：Skill Config API 读写与热重载。"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

import hub.api.server as srv  # noqa: E402


class FakeSkillConfig:
    def __init__(self):
        self.data = {"process_defaults": {"max_gate_retries": 3}}

    def get_all(self):
        return self.data

    def update_all(self, data):
        self.data = data


def test_skill_config_api_alias_and_reload(monkeypatch):
    fake = FakeSkillConfig()
    reloaded = {"n": 0}

    def reload():
        reloaded["n"] += 1

    monkeypatch.setattr(srv, "skill_config", fake)
    monkeypatch.setattr("common.skill_settings.reload_skill_settings", reload)

    client = TestClient(srv.app)
    assert client.get("/api/skill-config").json()["config"] == fake.data
    assert client.get("/api/skill_config").json()["config"] == fake.data

    new_cfg = {"process_defaults": {"max_gate_retries": 5, "hard_idle_sec": 99}}
    r = client.put("/api/skill_config", json={"config": new_cfg})
    assert r.status_code == 200
    assert r.json()["success"] is True
    assert fake.data == new_cfg
    assert reloaded["n"] == 1
