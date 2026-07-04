"""协作 skill 配置 — config/skill_config.json。"""

import json
from typing import Any

from common.paths import SKILL_CONFIG_FILE

DEFAULT_SKILL_CONFIG = {
    "notifications": {
        "enable_telegram": False,
        "use_project_group": True,
    },
    "hub": {
        "url": "http://127.0.0.1:8765",
    },
    "executor": {
        "poll_interval": 5,
        "ack_timeout": 300,
        "task_timeout": 3600,
        "team_config_timeout": 600,
        "task_plan_timeout": 600,
        "agent_msg_timeout": 1800,
        "max_retries": 3,
    },
    "auto_group": {
        "enabled": True,
        "include_main": True,
        "name_prefix": "",
    },
    "process_defaults": {
        "max_gate_retries": 5,
        "split_enabled": False,
        "soft_idle_sec": 240,
        "hard_idle_sec": 900,
        "max_cycles": 3,
        "parallel_enabled": False,
        "max_parallel": 3,
        "max_concurrent_projects": 2,
        "default_project_budget": 1000000,
        "budget_degrade_threshold": 0.8,
        "budget_degrade_backend": "",
        "budget_degrade_model": "",
    },
    "group_discussion": {
        "default_max_rounds": 3,
        "max_rounds_cap": 50,
        "roundtable_turn_timeout": 300,
        "quorum_ratio": 0.667,
        "auto_finalize_on_max_rounds": True,
        "allow_round_extension": True,
        "kill_cli_on_cancel": True,
        "terminate_commands": [
            "/终止讨论",
            "/终止圆桌",
            "/stop roundtable",
        ],
    },
}


class SkillConfig:
    def __init__(self):
        self._data: dict = {}
        self._load()

    def _load(self):
        SKILL_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        if SKILL_CONFIG_FILE.exists():
            try:
                with open(SKILL_CONFIG_FILE, encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}
        if not self._data:
            self._data = {}
            self._deep_merge(self._data, DEFAULT_SKILL_CONFIG)
            self._save()

    def _save(self):
        with open(SKILL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def _deep_merge(self, target: dict, source: dict):
        for key, val in source.items():
            if key not in target:
                target[key] = val
            elif isinstance(val, dict) and isinstance(target.get(key), dict):
                self._deep_merge(target[key], val)

    def get(self, *keys: str, default: Any = None) -> Any:
        val = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
                if val is None:
                    return default
            else:
                return default
        return val

    def get_all(self) -> dict:
        return self._data

    def update_all(self, data: dict):
        self._data = data
        self._save()


skill_config = SkillConfig()
