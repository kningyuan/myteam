#!/usr/bin/env python3
"""memstack Phase 0/1 测试 — TC-0-01~06。"""
from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_tc_0_01_imports():
    import memstack
    import memstack.kb
    import memstack.l1
    import memstack.facade
    import memstack.preferences
    import memstack.orchestration

    assert memstack is not None
    assert memstack.kb.list_kb_backends()
    assert memstack.l1.list_l1_backends()


def test_tc_0_03_kb_sqlite_roundtrip(tmp_path):
    from common.store.store import Store
    from memstack.kb import KB_SCHEME, get_kb_backend

    store = Store(tmp_path / "s.db")
    kb = get_kb_backend(store, backend="sqlite")
    ref = kb.write("pro_x", "GEO 结论", "结构化数据是关键", tags=["geo"])
    assert ref.startswith(f"{KB_SCHEME}sqlite/")
    got = kb.get(ref)
    assert got["title"] == "GEO 结论"
    found = kb.search(tags=["geo"], project_id="pro_x")
    assert found and found[0]["ref"] == ref
    store.close()
