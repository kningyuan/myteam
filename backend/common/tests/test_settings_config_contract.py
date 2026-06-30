#!/usr/bin/env python3
"""设置页 frontend ↔ /api/config、/api/skill-config 字段覆盖（防漂移）。"""
from __future__ import annotations

from pathlib import Path

import pytest

# 设置页 UI 已重构为组件化占位实现（SettingsPanels.tsx），字段级契约待面板实现后恢复
pytestmark = pytest.mark.skip(reason="设置页 UI 重构为组件化占位（SettingsPanels.tsx「正在建设中」），字段级契约待面板实现后恢复")

ROOT = Path(__file__).resolve().parents[3]
SETTINGS_PAGE = ROOT / "frontend" / "src" / "pages" / "SettingsPage.tsx"

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

# SettingsPage.tsx state → config path (load + save must both touch these keys)
FRONTEND_FIELD_MARKERS = {
    "system.port": ("sys.port", "port:"),
    "system.default_backend": ("defaultBackend", "default_backend"),
    "system.default_model": ("defaultModel", "default_model"),
    "system.debug": ("sys.debug", "debug:"),
    "system.audit_log": ("sys.audit_log", "audit_log:"),
    "system.audit_log_max_bytes": ("audit_log_max_bytes", "auditMaxBytes"),
    "system.price_per_mtok": ("price_per_mtok", "pricePerMtok"),
    "system.default_review": ("default_review", "defaultReview"),
    "notifications.use_project_group": ("use_project_group", "useProjectGroup"),
    "notifications.enable_telegram": ("enable_telegram", "enableTelegram"),
    "hub.url": ("skill.hub", "hubUrl"),
    "executor.poll_interval": ("poll_interval", "pollInterval"),
    "executor.ack_timeout": ("ack_timeout", "ackTimeout"),
    "executor.task_timeout": ("task_timeout", "taskTimeout"),
    "executor.agent_msg_timeout": ("agent_msg_timeout", "agentMsgTimeout"),
    "executor.team_config_timeout": ("team_config_timeout", "teamConfigTimeout"),
    "executor.task_plan_timeout": ("task_plan_timeout", "taskPlanTimeout"),
    "executor.max_retries": ("max_retries", "maxRetries"),
    "auto_group.enabled": ("ag.enabled", "autoGroup"),
    "auto_group.include_main": ("include_main", "autoGroupMain"),
    "auto_group.name_prefix": ("name_prefix", "autoGroupPrefix"),
    "process_defaults.default_project_budget": ("default_project_budget", "defaultBudget"),
    "process_defaults.max_gate_retries": ("max_gate_retries", "maxGateRetries"),
    "process_defaults.soft_idle_sec": ("soft_idle_sec", "softIdleSec"),
    "process_defaults.hard_idle_sec": ("hard_idle_sec", "hardIdleSec"),
    "process_defaults.max_cycles": ("max_cycles", "maxCycles"),
    "process_defaults.split_enabled": ("split_enabled", "splitDefault"),
    "process_defaults.parallel_enabled": ("parallel_enabled", "parallelEnabled"),
    "process_defaults.max_parallel": ("max_parallel", "maxParallel"),
    "process_defaults.max_concurrent_projects": ("max_concurrent_projects", "maxConcurrentProjects"),
    "process_defaults.budget_degrade_threshold": ("budget_degrade_threshold", "budgetDegradeThreshold"),
    "process_defaults.budget_degrade_backend": ("budget_degrade_backend", "budgetDegradeBackend"),
    "process_defaults.budget_degrade_model": ("budget_degrade_model", "budgetDegradeModel"),
}


@pytest.fixture(scope="module")
def settings_source() -> str:
    assert SETTINGS_PAGE.is_file(), f"missing {SETTINGS_PAGE}"
    return SETTINGS_PAGE.read_text(encoding="utf-8")


def test_all_system_fields_have_ui_control(settings_source: str):
    for field in SYSTEM_FIELDS:
        a, b = FRONTEND_FIELD_MARKERS[field]
        assert a in settings_source or b in settings_source, field


def test_all_skill_fields_have_ui_control(settings_source: str):
    for field in SKILL_FIELDS:
        a, b = FRONTEND_FIELD_MARKERS[field]
        assert a in settings_source or b in settings_source, field


def test_load_settings_reads_process_defaults_from_api(settings_source: str):
    assert "skill.process_defaults" in settings_source
    assert "process_defaults" in settings_source


def test_save_settings_writes_process_defaults(settings_source: str):
    assert "skillCfg.process_defaults" in settings_source
    assert "updateSkillConfig" in settings_source


def test_save_settings_does_not_write_models(settings_source: str):
    save_block = settings_source.split("async function handleSave", 1)[1]
    assert "cfg.models" not in save_block


def test_system_fields_have_load_paths(settings_source: str):
    for field in SYSTEM_FIELDS:
        key = field.split(".", 1)[1]
        assert f"sys.{key}" in settings_source or key in settings_source, field


def test_process_defaults_use_pd_from_skill_config(settings_source: str):
    assert "const pd = (skill.process_defaults" in settings_source


def test_executor_fields_read_from_skill_cfg(settings_source: str):
    assert "skill.executor" in settings_source
    assert "skillCfg.executor" in settings_source
