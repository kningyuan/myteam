#!/usr/bin/env python3
"""Claude adapter list_models：内置目录与 system_config 合并。"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from adapter.claude.adapter import ClaudeCodeAdapter, _merge_claude_models  # noqa: E402


def test_merge_includes_builtin_aliases_and_full_ids():
    models = _merge_claude_models([])
    ids = [m.id for m in models]
    assert "sonnet" in ids
    assert "opus" in ids
    assert "claude-sonnet-4-6[1M]" in ids
    assert len(ids) >= 10


def test_merge_config_extends_without_replacing_catalog(monkeypatch):
    models = _merge_claude_models([
        {"id": "custom-proxy-model", "name": "代理模型", "default": True},
    ])
    ids = [m.id for m in models]
    assert "sonnet" in ids
    assert "custom-proxy-model" in ids
    assert any(m.id == "custom-proxy-model" and m.default for m in models)


def test_list_models_uses_catalog_when_config_empty(monkeypatch):
    import config_store.system_config as sc

    monkeypatch.setattr(sc.system_config, "get_models", lambda b="claude": [])
    monkeypatch.setattr(sc.system_config, "get_default_model", lambda b="claude": "")
    models = ClaudeCodeAdapter().list_models()
    assert len(models) >= 10
    assert any(m.id == "sonnet" and m.default for m in models)
