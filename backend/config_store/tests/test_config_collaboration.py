"""跨模块协作测试 — skill_config → kernel_config, system_config → hub 默认端口。"""

from __future__ import annotations

import json


from config_store.system_config import DEFAULT_CONFIG


class TestSkillConfigReachesKernelConfig:
    """skill_config.executor 默认值应通过 kernel_config 影响 WatchdogConfig。"""

    def test_executor_timeout_reaches_watchdog(self, tmp_path, monkeypatch):
        from config_store import skill_config as sc
        from common.runtime.kernel_config import kernel_configs_for_run
        from common.skill.skill_settings import reload_skill_settings

        cfg_path = tmp_path / "skill_config.json"
        cfg_path.write_text(json.dumps({
            "executor": {
                "task_timeout": 9999,
                "poll_interval": 88,
                "max_retries": 5,
                "team_config_timeout": 600,
                "task_plan_timeout": 600,
                "agent_msg_timeout": 1800,
                "ack_timeout": 300,
            },
        }), encoding="utf-8")

        monkeypatch.setattr(sc, "SKILL_CONFIG_FILE", cfg_path)
        monkeypatch.setattr("common.skill.skill_settings.CONFIG_DIR", tmp_path)
        reload_skill_settings()

        sc.skill_config._data = {}
        sc.skill_config._load()

        _, wdog = kernel_configs_for_run(
            {"max_gate_retries": 5},
            mode="one_shot", backend="opencode",
        )

        assert wdog.kind_hard_idle["execute"] == 9999.0
        assert wdog.poll_interval == 88.0
        assert wdog.max_attempts == 5

    def test_executor_partial_defaults(self, tmp_path, monkeypatch):
        from config_store import skill_config as sc
        from common.runtime.kernel_config import kernel_configs_for_run
        from common.skill.skill_settings import reload_skill_settings

        cfg_path = tmp_path / "skill_config.json"
        cfg_path.write_text(json.dumps({
            "executor": {"task_timeout": 5555},
        }), encoding="utf-8")

        monkeypatch.setattr(sc, "SKILL_CONFIG_FILE", cfg_path)
        monkeypatch.setattr("common.skill.skill_settings.CONFIG_DIR", tmp_path)
        reload_skill_settings()

        sc.skill_config._data = {}
        sc.skill_config._load()

        _, wdog = kernel_configs_for_run(
            {"max_gate_retries": 3},
            mode="one_shot", backend="opencode",
        )

        assert wdog.kind_hard_idle["execute"] == 5555.0
        assert wdog.kind_hard_idle["triage"] == 300.0


class TestSystemConfigPortConsistency:
    """system_config 默认端口 8765 与 Hub 默认端口一致。"""

    def test_default_port_matches_hub_default(self):
        assert DEFAULT_CONFIG["system"]["port"] == 8765

    def test_get_port_returns_default(self, tmp_path, monkeypatch):
        from config_store import system_config as sc

        cfg_path = tmp_path / "system_config.json"
        monkeypatch.setattr(sc, "SYSTEM_CONFIG_FILE", cfg_path)
        sc.system_config._data = {}
        sc.system_config._load()

        port = sc.system_config.get("system", "port")
        assert port == 8765

    def test_custom_port(self, tmp_path, monkeypatch):
        from config_store import system_config as sc

        cfg_path = tmp_path / "system_config.json"
        monkeypatch.setattr(sc, "SYSTEM_CONFIG_FILE", cfg_path)
        sc.system_config._data = {}
        sc.system_config._load()

        sc.system_config.update_all({"system": {"port": 9999}, "backends": {}})
        assert sc.system_config.get("system", "port") == 9999

    def test_deputy_agent_id_default(self):
        assert DEFAULT_CONFIG["system"]["deputy_agent_id"] == "deputy"