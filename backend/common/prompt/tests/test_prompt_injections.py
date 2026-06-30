#!/usr/bin/env python3
"""prompt_injections + PromptComposer tests。"""
from __future__ import annotations

from pathlib import Path

import pytest

from common.prompt.prompt_composer import compose_execute_layers
from common.prompt.prompt_injections import (
    append_prompt_injections,
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
    from common.agent.agent_transport import build_worker_prompt
    from common.contracts import parse_request

    req = parse_request({
        "interaction_id": "i1", "kind": "execute", "project_id": "pro_x",
        "task_id": "t-req", "agent_id": "product", "intent": "写 PRD",
        "input": {"deliverable_path": "t-req_deliverable.md"},
        "constraints": {"task_type": "requirements"},
        "response_schema": "execute.result@1.0",
    })
    prompt = build_worker_prompt(req, Path("/tmp/i1.response"), Path("/tmp/deliv"))
    assert "light_v1" in prompt
    assert "align.md" in prompt
    assert "catalog" not in prompt or "means 自选" not in prompt


def test_compose_diagram_includes_all_and_means():
    from common.agent.agent_transport import build_worker_prompt
    from common.contracts import parse_request

    req = parse_request({
        "interaction_id": "i1", "kind": "execute", "project_id": "pro_x",
        "task_id": "t-diagram", "agent_id": "arch", "intent": "画图",
        "input": {"deliverable_path": "t-diagram_deliverable.md"},
        "constraints": {"task_type": "diagram-build"},
        "response_schema": "execute.result@1.0",
    })
    prompt = build_worker_prompt(req, Path("/tmp/i1.response"), Path("/tmp/deliv"))
    assert "all_v1" in prompt
    assert "means 自选" in prompt or "catalog" in prompt
    assert "verify_diagram" in prompt
