#!/usr/bin/env python3
"""submit_result 编排派发门测试。"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common import submit_result  # noqa: E402
from common.submit_result import DISPATCH_TOKEN_ENV, SubmitError  # noqa: E402

# 模块加载时保存真实 submit（conftest autouse 会在用例前包一层 bypass）
_REAL_SUBMIT = submit_result.submit


def _valid_body(iid: str) -> dict:
    return {
        "interaction_id": iid,
        "kind": "team_config",
        "status": "ok",
        "result": {"agents": ["main"]},
    }


def test_dispatch_gate_rejects_without_token(tmp_path, monkeypatch):
    iid = "p1:t1:team_config:1"
    resp = tmp_path / ".response" / f"{iid}.response"
    trigger = tmp_path / ".trigger" / f"{iid}.request"
    trigger.parent.mkdir(parents=True)
    trigger.write_text("{}", encoding="utf-8")
    monkeypatch.delenv(DISPATCH_TOKEN_ENV, raising=False)
    with pytest.raises(SubmitError, match="派发令牌"):
        _REAL_SUBMIT(_valid_body(iid), resp, require_dispatch=True)


def test_dispatch_gate_rejects_token_mismatch(tmp_path, monkeypatch):
    iid = "p1:t1:team_config:1"
    resp = tmp_path / ".response" / f"{iid}.response"
    trigger = tmp_path / ".trigger" / f"{iid}.request"
    trigger.parent.mkdir(parents=True)
    trigger.write_text("{}", encoding="utf-8")
    monkeypatch.setenv(DISPATCH_TOKEN_ENV, "wrong-id")
    with pytest.raises(SubmitError, match="派发令牌"):
        _REAL_SUBMIT(_valid_body(iid), resp, require_dispatch=True)


def test_dispatch_gate_rejects_missing_request(tmp_path, monkeypatch):
    iid = "p1:t1:team_config:1"
    resp = tmp_path / ".response" / f"{iid}.response"
    monkeypatch.setenv(DISPATCH_TOKEN_ENV, iid)
    with pytest.raises(SubmitError, match="派发请求"):
        _REAL_SUBMIT(_valid_body(iid), resp, require_dispatch=True)


def test_dispatch_gate_accepts_valid_dispatch(tmp_path, monkeypatch):
    iid = "p1:t1:team_config:1"
    resp = tmp_path / ".response" / f"{iid}.response"
    trigger = tmp_path / ".trigger" / f"{iid}.request"
    trigger.parent.mkdir(parents=True)
    trigger.write_text(json.dumps({"interaction_id": iid}), encoding="utf-8")
    monkeypatch.setenv(DISPATCH_TOKEN_ENV, iid)
    out = _REAL_SUBMIT(_valid_body(iid), resp, require_dispatch=True)
    assert out == resp
    assert json.loads(resp.read_text(encoding="utf-8"))["interaction_id"] == iid


def test_require_dispatch_false_bypasses_gate(tmp_path, monkeypatch):
    iid = "p1:t1:team_config:1"
    resp = tmp_path / "anywhere" / f"{iid}.response"
    monkeypatch.delenv(DISPATCH_TOKEN_ENV, raising=False)
    out = _REAL_SUBMIT(_valid_body(iid), resp, require_dispatch=False)
    assert out.exists()
