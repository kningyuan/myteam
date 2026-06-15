"""common 测试：框架内 submit() 绕过编排派发门（单测不走 AgentPort CLI）。"""
from __future__ import annotations

import sys

import pytest


@pytest.fixture(autouse=True)
def _framework_submit_bypass(monkeypatch):
    from common import submit_result

    _orig = submit_result.submit

    def _wrap(response, response_path, *, require_dispatch=True):
        return _orig(response, response_path, require_dispatch=False)

    monkeypatch.setattr(submit_result, "submit", _wrap)
    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        if getattr(mod, "submit", None) is _orig:
            monkeypatch.setattr(mod, "submit", _wrap)
