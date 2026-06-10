#!/usr/bin/env python3
"""Web 设置 Tab ↔ 运行时贯通测试（CHECK_ONLY，无 CLI）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.kernel_config import kernel_configs_for_run, watchdog_from_defaults  # noqa: E402
from common.skill_settings import (  # noqa: E402
    agent_msg_timeout,
    hub_base_url,
    is_auto_group_enabled,
    is_project_group_enabled,
    reload_skill_settings,
)


@pytest.fixture()
def skill_cfg(tmp_path, monkeypatch):
    cfg = {
        "hub": {"url": "http://test-hub:9999"},
        "executor": {
            "poll_interval": 2,
            "ack_timeout": 111,
            "task_timeout": 2222,
            "team_config_timeout": 333,
            "task_plan_timeout": 444,
            "agent_msg_timeout": 555,
            "max_retries": 2,
        },
        "notifications": {"use_project_group": True},
        "auto_group": {"enabled": True, "include_main": True},
        "process_defaults": {
            "max_gate_retries": 4,
            "soft_idle_sec": 88,
            "hard_idle_sec": 222,
            "max_concurrent_projects": 3,
            "parallel_enabled": True,
            "max_parallel": 2,
        },
    }
    path = tmp_path / "skill_config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setattr("common.skill_settings.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("common.paths.CONFIG_DIR", tmp_path)
    reload_skill_settings()
    yield cfg
    reload_skill_settings()


def test_executor_timeouts_reach_watchdog(skill_cfg):
    """设置 Tab executor.* → WatchdogConfig（Hub 启动 kernel 同源）。"""
    pd = skill_cfg["process_defaults"]
    wdog = watchdog_from_defaults(pd, skill_cfg["executor"])
    assert wdog.poll_interval == 2.0
    assert wdog.max_attempts == 2
    assert wdog.kind_hard_idle["execute"] == 2222.0
    assert wdog.kind_hard_idle["team_config"] == 333.0
    assert wdog.kind_hard_idle["task_plan"] == 444.0
    assert wdog.kind_hard_idle["triage"] == 111.0
    assert wdog.soft_idle_sec == 88.0
    assert wdog.hard_idle_sec == 222.0


def test_process_defaults_reach_process_config(skill_cfg):
    pd = skill_cfg["process_defaults"]
    proc, _ = kernel_configs_for_run(pd, mode="one_shot", backend="claude")
    assert proc.max_gate_retries == 4
    assert proc.parallel_enabled is True
    assert proc.max_parallel == 2


def test_executor_loaded_when_only_process_defaults_passed(skill_cfg):
    """Hub 只传 process_defaults 时仍须读到 executor（修复贯通 bug）。"""
    pd = skill_cfg["process_defaults"]
    _, wdog = kernel_configs_for_run(pd, mode="one_shot")
    assert wdog.kind_hard_idle["execute"] == 2222.0


def test_hub_url_helper(skill_cfg):
    assert hub_base_url() == "http://test-hub:9999"


def test_agent_msg_timeout_helper(skill_cfg):
    assert agent_msg_timeout() == 555


def test_notification_toggles(skill_cfg):
    assert is_project_group_enabled() is True
    assert is_auto_group_enabled() is True


def test_max_concurrent_projects_in_process_defaults(skill_cfg):
    assert skill_cfg["process_defaults"]["max_concurrent_projects"] == 3


def test_max_concurrent_from_settings(skill_cfg, monkeypatch):
    from common.project_runtime import _max_concurrent

    assert _max_concurrent() == 3


def test_audit_log_reads_system_config(tmp_path, monkeypatch):
    from common.audit_log import audit_enabled
    from store import system_config as sc

    cfg_path = tmp_path / "system_config.json"
    cfg_path.write_text(json.dumps({"system": {"audit_log": True}}), encoding="utf-8")
    monkeypatch.setattr(sc, "SYSTEM_CONFIG_FILE", cfg_path)
    sc.system_config._load()
    assert audit_enabled() is True
