#!/usr/bin/env python3
"""OpenCodeAdapter.list_models：动态查 `opencode models` + 解析 + 默认标记 + 回退。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import adapters.opencode.adapter as adp  # noqa: E402
from store.system_config import system_config  # noqa: E402


def _reset_cache():
    adp.OpenCodeAdapter._models_cache = []
    adp.OpenCodeAdapter._models_cache_ts = 0.0


def test_list_models_dynamic_parses_and_marks_default(tmp_path, monkeypatch):
    cli = tmp_path / "opencode"
    cli.write_text("x")
    monkeypatch.setattr(adp.OpenCodeAdapter, "_cli_path", lambda self: str(cli))

    class R:
        stdout = "opencode/big-pickle\nSenseNova/sensenova-6.7-flash-lite\n\n"
    monkeypatch.setattr(adp.subprocess, "run", lambda *a, **k: R())
    monkeypatch.setattr(system_config, "get_default_model",
                        lambda b="opencode": "SenseNova/sensenova-6.7-flash-lite")
    _reset_cache()

    models = adp.OpenCodeAdapter().list_models()
    by_id = {m.id: m for m in models}
    assert [m.id for m in models] == ["opencode/big-pickle",
                                      "SenseNova/sensenova-6.7-flash-lite"]
    assert by_id["SenseNova/sensenova-6.7-flash-lite"].provider == "SenseNova"
    assert by_id["SenseNova/sensenova-6.7-flash-lite"].default is True
    assert by_id["opencode/big-pickle"].provider == "opencode"
    assert by_id["opencode/big-pickle"].default is False


def test_list_models_falls_back_when_cli_fails(tmp_path, monkeypatch):
    cli = tmp_path / "opencode"
    cli.write_text("x")
    monkeypatch.setattr(adp.OpenCodeAdapter, "_cli_path", lambda self: str(cli))

    def boom(*a, **k):
        raise OSError("cli unavailable")
    monkeypatch.setattr(adp.subprocess, "run", boom)
    monkeypatch.setattr(system_config, "get_models", lambda b="opencode": [])
    _reset_cache()

    models = adp.OpenCodeAdapter().list_models()
    assert models and any("mimo" in m.id for m in models)
    _reset_cache()
