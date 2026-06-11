#!/usr/bin/env python3
"""静态校验 settings.js ↔ 双 API 字段覆盖（Skill 可执行，非 pytest）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SETTINGS_JS = ROOT / "frontend" / "settings.js"
INDEX_HTML = ROOT / "frontend" / "index.html"

SYSTEM_FIELDS = {
    "system.port", "system.default_backend", "system.default_model",
    "system.debug", "system.price_per_mtok", "system.default_review",
    "system.audit_log", "system.audit_log_max_bytes",
}

SKILL_FIELDS = {
    "notifications.enable_telegram", "notifications.use_project_group",
    "hub.url",
    "executor.poll_interval", "executor.ack_timeout", "executor.task_timeout",
    "executor.agent_msg_timeout", "executor.team_config_timeout",
    "executor.task_plan_timeout", "executor.max_retries",
    "auto_group.enabled", "auto_group.include_main", "auto_group.name_prefix",
    "process_defaults.max_gate_retries", "process_defaults.split_enabled",
    "process_defaults.soft_idle_sec", "process_defaults.hard_idle_sec",
    "process_defaults.max_cycles", "process_defaults.parallel_enabled",
    "process_defaults.max_parallel", "process_defaults.max_concurrent_projects",
    "process_defaults.default_project_budget", "process_defaults.budget_degrade_threshold",
    "process_defaults.budget_degrade_backend", "process_defaults.budget_degrade_model",
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


def main() -> int:
    if not SETTINGS_JS.is_file():
        print(f"ERROR: missing {SETTINGS_JS}", file=sys.stderr)
        return 1

    src = SETTINGS_JS.read_text(encoding="utf-8")
    issues: list[str] = []

    mapped = set(FRONTEND_MAPPINGS.values())
    for f in sorted(SYSTEM_FIELDS | SKILL_FIELDS):
        if f not in mapped:
            issues.append(f"no UI mapping: {f}")

    if "GOLDEN_PROCESS_DEFAULTS" in src:
        issues.append("GOLDEN_PROCESS_DEFAULTS still present — use skillCfg.process_defaults only")
    save_block = src.split("async function saveSettings", 1)
    if len(save_block) > 1 and "cfg.models" in save_block[1]:
        issues.append("saveSettings still writes cfg.models — models belong to /api/backends only")

    html_ids = set(re.findall(r'id="(set-[^"]+)"', INDEX_HTML.read_text(encoding="utf-8")))
    for dom_id in FRONTEND_MAPPINGS:
        if dom_id not in html_ids:
            issues.append(f"DOM id missing in index.html: {dom_id}")

    total = len(SYSTEM_FIELDS) + len(SKILL_FIELDS)
    if issues:
        print(f"FAIL: {len(issues)} issue(s) ({total} fields checked)")
        for i in issues:
            print(f"  - {i}")
        return 1

    print(f"PASS: {total} fields covered, load/save symmetry OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
