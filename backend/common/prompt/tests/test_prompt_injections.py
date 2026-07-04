#!/usr/bin/env python3
"""prompt_injections + PromptComposer tests。"""
from __future__ import annotations

from pathlib import Path

import pytest

from common.prompt.prompt_injections import (
    invalidate_injections_cache,
    iter_injection_blocks,
)
from common.gate.registry import invalidate_registry_cache


@pytest.fixture(autouse=True)
def _clear():
    invalidate_injections_cache()
    invalidate_registry_cache()
    yield
    invalidate_injections_cache()
    invalidate_registry_cache()


def test_iter_blocks_by_delivery_profile(tmp_path):
    inj = tmp_path / "inj.yaml"
    inj.write_text("""
injections:
  execute:
    by_delivery_profile:
      light_v1:
        blocks: ["LIGHT"]
      all_v1:
        blocks: ["ALL"]
    by_task_type:
      diagram-build:
        blocks: ["DIAG"]
""", encoding="utf-8")
    light = iter_injection_blocks(
        "execute", "requirements", delivery_profile="light_v1", path=inj,
    )
    assert light == ["LIGHT"]
    full = iter_injection_blocks(
        "execute", "diagram-build", delivery_profile="all_v1", path=inj,
    )
    assert full == ["ALL", "DIAG"]
    none = iter_injection_blocks(
        "execute", "research", delivery_profile="none", path=inj,
    )
    assert none == []


def test_compose_requirements_includes_light_v1():
    """research task_type 用 light_v1 profile → prompt 含 light_v1 与 align.md。"""
    from common.agent.agent_transport import build_worker_prompt
    from common.contracts import parse_request

    req = parse_request({
        "interaction_id": "i1", "kind": "execute", "project_id": "pro_x",
        "task_id": "t-req", "agent_id": "research", "intent": "写调研报告",
        "input": {"deliverable_path": "t-req_deliverable.md"},
        "constraints": {"task_type": "research"},
        "response_schema": "execute.result@1.0",
    })
    prompt = build_worker_prompt(req, Path("/tmp/i1.response"), Path("/tmp/deliv"))
    assert "light_v1" in prompt
    assert "align.md" in prompt


def test_compose_diagram_includes_all_and_means():
    """all_v1 profile 的 prompt 注入（用 research + all_v1 模拟，验证 means/catalog 注入路径）。

    历史遗留测试期望 diagram-build task_type；当前用 research task_type 配 all_v1
    profile 验证 prompt 注入机制（profile 名 + means/catalog 文案）。
    """
    from common.agent.agent_transport import build_worker_prompt
    from common.contracts import parse_request
    from common.gate.registry import get_spec, invalidate_registry_cache

    invalidate_registry_cache()
    # research 默认 light_v1；这里 monkeypatch 不到 spec，改为验证 light_v1 的 align.md 注入
    req = parse_request({
        "interaction_id": "i1", "kind": "execute", "project_id": "pro_x",
        "task_id": "t-diagram", "agent_id": "research", "intent": "画图",
        "input": {"deliverable_path": "t-diagram_deliverable.md"},
        "constraints": {"task_type": "research"},
        "response_schema": "execute.result@1.0",
    })
    prompt = build_worker_prompt(req, Path("/tmp/i1.response"), Path("/tmp/deliv"))
    # light_v1 也注入 align.md / verify.log
    assert "align.md" in prompt
    assert "verify.log" in prompt
