"""common 测试：框架内 submit() 绕过编排派发门（单测不走 AgentPort CLI）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TEST_TASK_TYPES = Path(__file__).resolve().parent / "fixtures" / "task_types.yaml"


@pytest.fixture(autouse=True)
def _test_task_type_registry(monkeypatch):
    """单测使用 fixtures/task_types.yaml，产品 templates.yaml 默认为空。"""
    if not _TEST_TASK_TYPES.is_file():
        yield
        return
    from common import paths
    from common.gate.registry import invalidate_registry_cache

    monkeypatch.setattr(paths, "templates_file", lambda: _TEST_TASK_TYPES)
    invalidate_registry_cache()
    yield
    invalidate_registry_cache()


@pytest.fixture(autouse=True)
def _framework_submit_bypass(monkeypatch):
    from common.delivery import submit_result

    _orig = submit_result.submit

    def _wrap(response, response_path, *, require_dispatch=True):
        return _orig(response, response_path, require_dispatch=False)

    monkeypatch.setattr(submit_result, "submit", _wrap)
    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        if getattr(mod, "submit", None) is _orig:
            monkeypatch.setattr(mod, "submit", _wrap)
