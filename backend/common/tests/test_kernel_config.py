#!/usr/bin/env python3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.agent_port import AgentPort, WatchdogConfig  # noqa: E402
from common.kernel_config import (  # noqa: E402
    kernel_configs_for_run,
    process_from_defaults,
    watchdog_from_defaults,
)
from common.process_types import ProcessConfig  # noqa: E402
from common.run_kernel import resume_project  # noqa: E402
from common.store import Store  # noqa: E402


def test_watchdog_from_defaults():
    w = watchdog_from_defaults({"soft_idle_sec": 90, "hard_idle_sec": 240})
    assert w.soft_idle_sec == 90.0
    assert w.hard_idle_sec == 240.0


def test_process_from_defaults_split_override():
    cfg = process_from_defaults({"split_enabled": False}, split=True, mode="recurring")
    assert cfg.split_enabled is True
    assert cfg.mode == "recurring"
    assert cfg.max_gate_retries == 5


def test_process_from_defaults_l3_budget():
    cfg = process_from_defaults({
        "budget_degrade_threshold": 0.75,
        "budget_degrade_backend": "claude",
        "budget_degrade_model": "haiku",
        "skill_extract_enabled": True,
    })
    assert cfg.budget_degrade_threshold == 0.75
    assert cfg.budget_degrade_backend == "claude"
    assert cfg.budget_degrade_model == "haiku"
    assert cfg.skill_extract_enabled is True


def test_process_from_defaults_skill_extract():
    cfg = process_from_defaults({"skill_extract_enabled": True})
    assert cfg.skill_extract_enabled is True


def test_kernel_configs_for_run_unified():
    """Hub / CLI 应共用 kernel_configs_for_run 构建双配置。"""
    proc, wdog = kernel_configs_for_run(
        {"max_gate_retries": 2, "soft_idle_sec": 45, "hard_idle_sec": 180},
        mode="recurring",
        token_budget=9000,
        backend="claude",
    )
    assert proc.max_gate_retries == 2
    assert proc.token_budget == 9000
    assert proc.mode == "recurring"
    assert proc.default_backend == "claude"
    assert wdog.soft_idle_sec == 45.0
    assert wdog.hard_idle_sec == 180.0


def test_resume_project_uses_kernel_configs_watchdog(tmp_path, monkeypatch):
    """resume 路径须与新建项目一样注入 skill_config.process_defaults → Watchdog。"""
    import common.paths as paths

    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "state.db")
    store.upsert_project("p_cfg", status="in_progress", meta={"goal": "g", "token_budget": 1000})
    store.upsert_task("p_cfg", "t1", agent="dev", task_type="research", status="pending")

    def fake_kernel_configs(**_kwargs):
        return ProcessConfig(token_budget=1000), WatchdogConfig(hard_idle_sec=99.0, soft_idle_sec=11.0)

    monkeypatch.setattr("common.kernel_config.kernel_configs_for_run", fake_kernel_configs)
    captured: dict = {}
    _orig_init = AgentPort.__init__

    def _cap_init(self, transport, store=None, config=None, **kwargs):
        captured["watchdog"] = config
        return _orig_init(self, transport, store=store, config=config, **kwargs)

    monkeypatch.setattr(AgentPort, "__init__", _cap_init)

    try:
        resume_project("p_cfg", store=store, transport=lambda ctx: None)
    except Exception:
        pass
    store.close()
    assert captured["watchdog"].hard_idle_sec == 99.0
    assert captured["watchdog"].soft_idle_sec == 11.0


def test_skill_settings_process_defaults_empty(tmp_path, monkeypatch):
    from common.paths import CONFIG_DIR
    from common.skill_settings import process_defaults, reload_skill_settings

    monkeypatch.setattr("common.skill_settings.CONFIG_DIR", tmp_path)
    reload_skill_settings()
    assert process_defaults() == {}

    cfg_path = tmp_path / "skill_config.json"
    cfg_path.write_text(
        '{"process_defaults": {"skill_extract_enabled": true, "max_gate_retries": 5}}',
        encoding="utf-8",
    )
    reload_skill_settings()
    assert process_defaults().get("skill_extract_enabled") is True
    assert process_defaults().get("max_gate_retries") == 5
