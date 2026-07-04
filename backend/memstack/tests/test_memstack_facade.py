#!/usr/bin/env python3
"""facade 测试 — TC-0-02, TC-0-06, TC-2-04。"""
from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.store.store import Store
from memstack.facade import inject_for_execute, on_task_success
from memstack.kb.protocol import KB_SCHEME
from memstack.kb.registry import get_kb_backend, register_kb_backend
from memstack.orchestration.context import ExecuteInjectContext, TaskSuccessContext


def test_tc_0_02_facade_disabled_no_extra_kb(monkeypatch, tmp_path):
    """memstack + execution_harness 均禁用时，不注入【相关知识】。"""
    monkeypatch.setenv("MEMSTACK_ENABLED_OVERRIDE", "")
    # 禁用 memstack（facade 层 + config 层）
    monkeypatch.setattr("memstack.facade.memstack_enabled", lambda default=False: False)
    monkeypatch.setattr("memstack.config.memstack_enabled", lambda default=False: False)
    # 禁用 execution_harness KB 注入（facade 委托到 execution_harness）
    monkeypatch.setattr("execution_harness.config.kb_inject_allowed", lambda default=True: False)
    store = Store(tmp_path / "s.db")
    lines: list[str] = []
    inject_for_execute(
        ExecuteInjectContext(
            lines=lines,
            project_id="p1",
            task_type="research",
            store=store,
        )
    )
    assert not any("【相关知识】" in ln for ln in lines)
    store.close()


def test_tc_0_06_mock_adapter_pluggable(tmp_path):
    class MockKB:
        name = "mock"

        def __init__(self, store=None):
            self.store = store
            self._n = 0

        def write(self, project_id, title, content, *, task_id="", tags=None):
            self._n += 1
            return f"{KB_SCHEME}mock/{self._n}"

        def get(self, ref):
            return {"ref": ref, "title": "mock", "content": "x"}

        def search(self, *, tags=None, text="", project_id=None):
            return [{"ref": f"{KB_SCHEME}mock/1", "title": "t", "content": "c"}]

    register_kb_backend("mock", MockKB)
    store = Store(tmp_path / "s.db")
    kb = get_kb_backend(store, backend="mock")
    ref = kb.write("p", "t", "body")
    assert ref.startswith(f"{KB_SCHEME}mock/")
    assert kb.search()
    store.close()


def test_on_task_success_no_ledger(tmp_path):
    store = Store(tmp_path / "s.db")
    base = tmp_path / "deliv"
    base.mkdir()
    ref = on_task_success(
        TaskSuccessContext(
            base_dir=base,
            project_id="p",
            task_id="t1",
            task_type="research",
            store=store,
        )
    )
    assert ref is None
    store.close()
