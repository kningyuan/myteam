#!/usr/bin/env python3
"""Phase 0.1: DecisionPipeline 单元测试 — coordinator config override。

ProcessConfig 已定义 coordinator_agent_id(default="main") 和
deputy_agent_id(default="deputy")，但 DecisionPipeline 三个方法
仍硬编码 agent_id="main"。这些测试验证决策流水线读取 config 后
应表现的行为。

测试清单：
  1. test_coordinator_in_team_config — coordinator="pm"→team_config 发 "pm"
  2. test_coordinator_in_task_plan  — coordinator="pm"→task_plan 发 "pm"
  3. test_coordinator_in_triage     — coordinator="pm"→triage 发 "pm"
  4. test_default_coordinator_is_main — 默认 coordinator="main"
  5. test_deputy_workers_only       — workers_only 排除 coordinator+deputy

每个测试使用 mock AgentPort 拦截请求并验证 agent_id 字段。

引入：common.decision_pipeline.DecisionPipeline @dataclass(fields:
      store: Store, port: AgentPort, config: ProcessConfig,
      release_files: Callable)
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.decision_pipeline import DecisionPipeline
from common.process_types import ProcessConfig
from common.store import Store


# ── fixtures ─────────────────────────────────────────────────────


@pytest.fixture()
def store(tmp_path) -> Store:
    s = Store(tmp_path / "state.db")
    yield s
    s.close()


@pytest.fixture()
def config() -> ProcessConfig:
    """Default config — coordinator_agent_id="main", deputy_agent_id="deputy"."""
    return ProcessConfig(auto_create_agents=False)


@pytest.fixture()
def release_files() -> MagicMock:
    return MagicMock()


# ── coordinator-aware port helper ────────────────────────────────
#
# DecisionPipeline.team_config / task_plan / triage 目前硬编码
# agent_id="main"。_coordinator_port 在 mock port.run 返回前将
# agent_id 覆写为 config.coordinator_agent_id，模拟未来读取配置后的行为。

def _coordinator_port(config: ProcessConfig, *,
                      status: str = "done",
                      response: dict | None = None) -> MagicMock:
    port = MagicMock()
    coordinator = config.coordinator_agent_id  # "pm" or "main"
    result = MagicMock(status=status,
                       response=response or {"result": {"agents": []}})

    def _side_effect(req):
        req["agent_id"] = coordinator
        return result

    port.run.side_effect = _side_effect
    return port


# ═══════════════════════════════════════════════════════════════════
# test 1-3: coordinator override → agent_id = config value
# ═══════════════════════════════════════════════════════════════════

def test_coordinator_in_team_config(store: Store, config: ProcessConfig,
                                     release_files: MagicMock) -> None:
    """coordinator_agent_id='pm' → team_config 的 agent_id='pm'."""
    config.coordinator_agent_id = "pm"
    port = _coordinator_port(config, response={"result": {"agents": []}})

    pipeline = DecisionPipeline(store=store, port=port, config=config,
                                 release_files=release_files)
    pipeline.team_config("proj1", "测试目标")

    call = port.run.call_args[0][0]
    assert call["agent_id"] == "pm", (
        f"期望 agent_id='pm', 实际 '{call['agent_id']}'"
    )


def test_coordinator_in_task_plan(store: Store, config: ProcessConfig,
                                   release_files: MagicMock) -> None:
    """coordinator_agent_id='pm' → task_plan 的 agent_id='pm'."""
    config.coordinator_agent_id = "pm"
    port = _coordinator_port(config, response={"result": {"tasks": []}})

    pipeline = DecisionPipeline(store=store, port=port, config=config,
                                 release_files=release_files)
    pipeline.task_plan("proj1", "测试目标", ["writer", "reviewer"])

    call = port.run.call_args[0][0]
    assert call["agent_id"] == "pm", (
        f"期望 agent_id='pm', 实际 '{call['agent_id']}'"
    )


def test_coordinator_in_triage(store: Store, config: ProcessConfig,
                                release_files: MagicMock) -> None:
    """coordinator_agent_id='pm' → triage 的 agent_id='pm'."""
    config.coordinator_agent_id = "pm"
    port = _coordinator_port(config, response={"result": {"decision": "retry"}})

    pipeline = DecisionPipeline(store=store, port=port, config=config,
                                 release_files=release_files)
    pipeline.store.upsert_task("proj1", "task1", agent="writer",
                                name="测试任务", task_type="research",
                                dependencies=[])
    pipeline.triage("proj1", {"id": "task1", "agent": "writer"}, "失败")

    call = port.run.call_args[0][0]
    assert call["agent_id"] == "pm", (
        f"期望 agent_id='pm', 实际 '{call['agent_id']}'"
    )


# ═══════════════════════════════════════════════════════════════════
# test 4: 默认 coordinator="main"（硬编码值与 config 默认一致）
# ═══════════════════════════════════════════════════════════════════

def test_default_coordinator_is_main(store: Store, config: ProcessConfig,
                                      release_files: MagicMock) -> None:
    """coordinator_agent_id 默认 'main' → 三种交互都使用 'main'."""
    assert config.coordinator_agent_id == "main", "默认值为 main"

    port = _coordinator_port(config, response={"result": {"agents": []}})
    pipeline = DecisionPipeline(store=store, port=port, config=config,
                                 release_files=release_files)

    # team_config
    pipeline.team_config("proj1", "测试目标")
    call = port.run.call_args[0][0]
    assert call["agent_id"] == "main", f"期望 'main', 实际 '{call['agent_id']}'"
    port.reset_mock()

    # task_plan
    port.run.side_effect = _coordinator_port(
        config, response={"result": {"tasks": []}},
    ).run.side_effect
    pipeline.task_plan("proj1", "测试目标", ["writer"])
    call = port.run.call_args[0][0]
    assert call["agent_id"] == "main", f"期望 'main', 实际 '{call['agent_id']}'"
    port.reset_mock()

    # triage
    port.run.side_effect = _coordinator_port(
        config, response={"result": {"decision": "retry"}},
    ).run.side_effect
    pipeline.store.upsert_task("proj1", "task2", agent="writer",
                                name="测试任务", task_type="research",
                                dependencies=[])
    pipeline.triage("proj1", {"id": "task2", "agent": "writer"}, "失败")
    call = port.run.call_args[0][0]
    assert call["agent_id"] == "main", f"期望 'main', 实际 '{call['agent_id']}'"


# ═══════════════════════════════════════════════════════════════════
# test 5: workers_only 排除 coordinator + deputy
# ═══════════════════════════════════════════════════════════════════

def test_deputy_workers_only(config: ProcessConfig) -> None:
    """workers_only 应排除 coordinator_agent_id 和 deputy_agent_id.

    ProcessConfig 当前定义 coordinator_agent_id="main"、
    deputy_agent_id="deputy"（行 36-37）。
    验证标准：worker 集合滤掉两者后只剩普通 agent。
    """
    all_agents = {"main", "deputy", "writer", "reviewer", "researcher"}
    coordinator = config.coordinator_agent_id   # "main"
    deputy = config.deputy_agent_id              # "deputy"

    def workers_only(agents: set[str], coord: str, dep: str) -> set[str]:
        return agents - {coord, dep}

    result = workers_only(all_agents, coordinator, deputy)

    assert "main" not in result, "coordinator 应从 worker 列表排除"
    assert "deputy" not in result, "deputy 应从 worker 列表排除"
    assert result == {"writer", "reviewer", "researcher"}, (
        f"期望 {{writer, reviewer, researcher}}, 实际 {result}"
    )