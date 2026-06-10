#!/usr/bin/env python3
"""设置页 settings.js ↔ /api/config、/api/skill-config 字段覆盖（防漂移）。"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SETTINGS_JS = ROOT / "frontend" / "settings.js"

SYSTEM_FIELDS = {
    "system.port",
    "system.default_backend",
    "system.default_model",
    "system.debug",
    "system.price_per_mtok",
    "system.default_review",
    "system.audit_log",
    "system.audit_log_max_bytes",
}

SKILL_FIELDS = {
    "notifications.enable_telegram",
    "notifications.use_project_group",
    "hub.url",
    "executor.poll_interval",
    "executor.ack_timeout",
    "executor.task_timeout",
    "executor.agent_msg_timeout",
    "executor.team_config_timeout",
    "executor.task_plan_timeout",
    "executor.max_retries",
    "auto_group.enabled",
    "auto_group.include_main",
    "auto_group.name_prefix",
    "process_defaults.max_gate_retries",
    "process_defaults.split_enabled",
    "process_defaults.soft_idle_sec",
    "process_defaults.hard_idle_sec",
    "process_defaults.max_cycles",
    "process_defaults.parallel_enabled",
    "process_defaults.max_parallel",
    "process_defaults.max_concurrent_projects",
    "process_defaults.default_project_budget",
    "process_defaults.budget_degrade_threshold",
    "process_defaults.budget_degrade_backend",
    "process_defaults.budget_degrade_model",
}

FRONTEND_MAPPINGS = {
    "set-port": "system.port",
    "set-default-backend": "system.default_backend",
    "set-default-model": "system.default_model",
    "set-debug": "system.debug",
    "set-audit-log": "system.audit_log",
    "set-audit-log-max-bytes": "system.audit_log_max_bytes",
    "set-price": "system.price_per_mtok",
    "set-default-review": "system.default_review",
    "set-model-aliases": "backends.opencode.model_aliases",
    "set-use-project-group": "notifications.use_project_group",
    "set-enable-telegram": "notifications.enable_telegram",
    "set-hub-url": "hub.url",
    "set-poll-interval": "executor.poll_interval",
    "set-ack-timeout": "executor.ack_timeout",
    "set-task-timeout": "executor.task_timeout",
    "set-agent-msg-timeout": "executor.agent_msg_timeout",
    "set-team-config-timeout": "executor.team_config_timeout",
    "set-task-plan-timeout": "executor.task_plan_timeout",
    "set-max-retries": "executor.max_retries",
    "set-auto-group": "auto_group.enabled",
    "set-auto-group-include-main": "auto_group.include_main",
    "set-auto-group-name-prefix": "auto_group.name_prefix",
    "set-default-budget": "process_defaults.default_project_budget",
    "set-max-gate-retries": "process_defaults.max_gate_retries",
    "set-soft-idle": "process_defaults.soft_idle_sec",
    "set-hard-idle": "process_defaults.hard_idle_sec",
    "set-max-cycles": "process_defaults.max_cycles",
    "set-split-default": "process_defaults.split_enabled",
    "set-parallel-default": "process_defaults.parallel_enabled",
    "set-max-parallel": "process_defaults.max_parallel",
    "set-max-concurrent-projects": "process_defaults.max_concurrent_projects",
    "set-budget-degrade-threshold": "process_defaults.budget_degrade_threshold",
    "set-budget-degrade-backend": "process_defaults.budget_degrade_backend",
    "set-budget-degrade-model": "process_defaults.budget_degrade_model",
}


@pytest.fixture(scope="module")
def settings_source() -> str:
    return SETTINGS_JS.read_text(encoding="utf-8")


def test_all_system_fields_have_ui_control():
    mapped = set(FRONTEND_MAPPINGS.values())
    missing = SYSTEM_FIELDS - mapped
    assert not missing, f"system fields without UI: {missing}"


def test_all_skill_fields_have_ui_control():
    mapped = set(FRONTEND_MAPPINGS.values())
    missing = SKILL_FIELDS - mapped
    assert not missing, f"skill fields without UI: {missing}"


def test_load_settings_reads_process_defaults_from_api(settings_source):
    assert "skillCfg.process_defaults" in settings_source
    assert "GOLDEN_PROCESS_DEFAULTS" not in settings_source


def test_save_settings_does_not_write_models(settings_source):
    save_block = settings_source.split("async function saveSettings", 1)[1]
    assert "cfg.models" not in save_block


def test_system_fields_have_load_paths(settings_source):
    for field in SYSTEM_FIELDS:
        key = field.split(".", 1)[1]
        assert f"cfg.system?.{key}" in settings_source or f"cfg.system.{key}" in settings_source


def test_process_defaults_use_pd_from_skill_config(settings_source):
    for field in SKILL_FIELDS:
        if not field.startswith("process_defaults."):
            continue
        key = field.split(".", 1)[1]
        assert f"pd.{key}" in settings_source, field


def test_executor_fields_read_from_skill_cfg(settings_source):
    for field in SKILL_FIELDS:
        if not field.startswith("executor."):
            continue
        key = field.split(".", 1)[1]
        assert f"skillCfg.executor?.{key}" in settings_source


def test_settings_dom_ids_exist_in_html():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    html_ids = set(re.findall(r'id="(set-[^"]+)"', html))
    for dom_id in FRONTEND_MAPPINGS:
        assert dom_id in html_ids, dom_id
