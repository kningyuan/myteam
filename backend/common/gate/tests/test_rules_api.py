#!/usr/bin/env python3
"""团队通用 rules API。"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

import hub.api.server as srv  # noqa: E402


def test_rules_shared_list_and_put(tmp_path, monkeypatch):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "ethos.md").write_text("# ethos\n", encoding="utf-8")
    monkeypatch.setattr("common.gate.shared_rules.RULES_DIR", rules_dir)
    touched = {"n": 0}
    monkeypatch.setattr(
        "common.observability.hub_operation_meta.touch",
        lambda *a, **k: touched.__setitem__("n", touched["n"] + 1),
    )

    client = TestClient(srv.app)
    r = client.get("/api/rules/shared")
    assert r.status_code == 200
    body = r.json()
    assert "ethos.md" in body["contents"]
    assert any(f["filename"] == "ethos.md" for f in body["files"])

    r2 = client.put("/api/rules/shared/ethos.md", json={"content": "# updated"})
    assert r2.status_code == 200
    assert r2.json()["success"] is True
    assert (rules_dir / "ethos.md").read_text(encoding="utf-8") == "# updated"
    assert touched["n"] == 1

    r3 = client.get("/api/rules/shared/ethos.md")
    assert r3.status_code == 200
    assert r3.json()["content"] == "# updated"


def test_rules_shared_get_missing_returns_404(tmp_path, monkeypatch):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    monkeypatch.setattr("common.gate.shared_rules.RULES_DIR", rules_dir)

    client = TestClient(srv.app)
    r = client.get("/api/rules/shared/missing.md")
    assert r.status_code == 404
