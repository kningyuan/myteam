#!/usr/bin/env python3
"""
P0/B1 + P1/C2-C3 回归测试：
- B1: budget_degrade_backend/model 空串短路
- C2-C3: models 字段从 DEFAULT_CONFIG 和 GET 响应中剥离
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.runtime.kernel_config import process_from_defaults  # noqa: E402
from common.skill.skill_settings import reload_skill_settings  # noqa: E402


# ============ B1: 空串短路 ============


class TestBudgetDegradeEmptyString:
    """P0/B1: budget_degrade_backend/model 空串应在后端短路。"""

    def test_empty_string_backend_passes_empty(self):
        """空字符串 → ProcessConfig.budget_degrade_backend == ''。"""
        cfg = process_from_defaults({"budget_degrade_backend": "", "budget_degrade_model": ""})
        assert cfg.budget_degrade_backend == ""
        assert cfg.budget_degrade_model == ""

    def test_none_values_passes_empty(self):
        """None → 短路为空串。"""
        cfg = process_from_defaults({"budget_degrade_backend": None, "budget_degrade_model": None})
        assert cfg.budget_degrade_backend == ""
        assert cfg.budget_degrade_model == ""

    def test_missing_keys_passes_empty(self):
        """缺失 key → 短路为空串。"""
        cfg = process_from_defaults({})
        assert cfg.budget_degrade_backend == ""
        assert cfg.budget_degrade_model == ""

    def test_whitespace_backend_short_circuits(self):
        """纯空格 → 短路为空串（非预期的合法 backend 名）。"""
        cfg = process_from_defaults({"budget_degrade_backend": "   ", "budget_degrade_model": "  "})
        assert cfg.budget_degrade_backend == ""
        assert cfg.budget_degrade_model == ""

    def test_valid_backend_preserved(self):
        """合法值应原样传递。"""
        cfg = process_from_defaults({
            "budget_degrade_backend": "claude",
            "budget_degrade_model": "sonnet-4",
        })
        assert cfg.budget_degrade_backend == "claude"
        assert cfg.budget_degrade_model == "sonnet-4"

    def test_non_empty_preserved(self):
        """非空非白串应保留。"""
        cfg = process_from_defaults({"budget_degrade_backend": "openai", "budget_degrade_model": "gpt-4"})
        assert cfg.budget_degrade_backend == "openai"
        assert cfg.budget_degrade_model == "gpt-4"

    def test_degrade_disabled_by_default(self):
        """默认情况下降级应禁用（空串 = 不改）。"""
        cfg = process_from_defaults({})
        assert cfg.budget_degrade_backend == ""
        assert cfg.budget_degrade_model == ""
        # process.py:_maybe_degrade_budget 中 `if not backend and not model: return`
        # 确保空串不会触发降级

    def test_threshold_unchanged(self):
        """阈值字段不应受 B1 变更影响。"""
        cfg = process_from_defaults({"budget_degrade_threshold": 0.9})
        assert cfg.budget_degrade_threshold == 0.9


# ============ C2-C3: models 字段剥离 ============


class TestModelsFieldStripped:
    """P1/C2-C3: models 字段不应出现在 DEFAULT_CONFIG 和 get_all() 中。"""

    def test_default_config_no_models_key(self):
        """DEFAULT_CONFIG 不应包含 'models' 键。"""
        from config_store.system_config import DEFAULT_CONFIG
        assert "models" not in DEFAULT_CONFIG

    def test_get_all_excludes_models(self, tmp_path, monkeypatch):
        """get_all() 返回的数据中不包含 models 键。"""
        from config_store import system_config as sc

        cfg_path = tmp_path / "system_config.json"
        # 写入包含 models 的旧配置文件
        cfg_path.write_text(json.dumps({
            "system": {"port": 8765, "default_backend": "opencode"},
            "backends": {"opencode": {"enabled": True, "cli_path": ""}},
            "models": {"opencode": [{"id": "test"}]},
        }), encoding="utf-8")
        monkeypatch.setattr(sc, "SYSTEM_CONFIG_FILE", cfg_path)
        sc.system_config._load()

        all_data = sc.system_config.get_all()
        assert "models" not in all_data
        # system 和 backends 仍然存在
        assert "system" in all_data
        assert "backends" in all_data

    def test_get_all_no_models_on_fresh_config(self, tmp_path, monkeypatch):
        """新生成的配置中也不包含 models。"""
        from config_store import system_config as sc

        cfg_path = tmp_path / "system_config.json"
        # 不创建文件，让 _load() 使用 DEFAULT_CONFIG
        if cfg_path.exists():
            cfg_path.unlink()
        monkeypatch.setattr(sc, "SYSTEM_CONFIG_FILE", cfg_path)
        sc.system_config._load()

        all_data = sc.system_config.get_all()
        assert "models" not in all_data

    def test_get_models_still_works_backward_compat(self, tmp_path, monkeypatch):
        """get_models() 仍应从 _data 中读取旧文件中的 models（向后兼容）。"""
        from config_store import system_config as sc

        cfg_path = tmp_path / "system_config.json"
        cfg_path.write_text(json.dumps({
            "system": {"port": 8765},
            "backends": {"opencode": {"enabled": True, "cli_path": ""}},
            "models": {
                "opencode": [
                    {"id": "legacy-model-1", "name": "Legacy 1", "default": True},
                    {"id": "legacy-model-2", "name": "Legacy 2"},
                ],
            },
        }), encoding="utf-8")
        monkeypatch.setattr(sc, "SYSTEM_CONFIG_FILE", cfg_path)
        sc.system_config._load()

        models = sc.system_config.get_models("opencode")
        assert len(models) == 2
        assert models[0]["id"] == "legacy-model-1"
        assert models[0]["default"] is True

    def test_get_models_returns_empty_for_new_config(self, tmp_path, monkeypatch):
        """新配置中 get_models() 返回空列表。"""
        from config_store import system_config as sc

        cfg_path = tmp_path / "system_config.json"
        if cfg_path.exists():
            cfg_path.unlink()
        monkeypatch.setattr(sc, "SYSTEM_CONFIG_FILE", cfg_path)
        # 重置 singleton 的数据（新配置文件不存在，_load 会使用 DEFAULT_CONFIG）
        sc.system_config._data = {}
        sc.system_config._load()

        models = sc.system_config.get_models("opencode")
        assert models == []

    def test_get_default_model_fallback(self, tmp_path, monkeypatch):
        """没有 models 时 get_default_model 回退到 system.default_model。"""
        from config_store import system_config as sc

        cfg_path = tmp_path / "system_config.json"
        cfg_path.write_text(json.dumps({
            "system": {"port": 8765, "default_model": "fallback-model"},
            "backends": {"opencode": {"enabled": True, "cli_path": ""}},
        }), encoding="utf-8")
        monkeypatch.setattr(sc, "SYSTEM_CONFIG_FILE", cfg_path)
        sc.system_config._load()

        default = sc.system_config.get_default_model("opencode")
        assert default == "fallback-model"

    def test_update_all_ignores_models_from_client(self, tmp_path, monkeypatch):
        """PUT 中的 models 被忽略；get_all() 仍剥离。"""
        from config_store import system_config as sc

        cfg_path = tmp_path / "system_config.json"
        cfg_path.write_text(json.dumps({
            "system": {"port": 8765},
            "backends": {"opencode": {"enabled": True, "cli_path": ""}},
        }), encoding="utf-8")
        monkeypatch.setattr(sc, "SYSTEM_CONFIG_FILE", cfg_path)
        sc.system_config._load()

        sc.system_config.update_all({
            "system": {"port": 8765},
            "backends": {"opencode": {"enabled": True, "cli_path": ""}},
            "models": {"opencode": [{"id": "new-model"}]},
        })

        all_data = sc.system_config.get_all()
        assert "models" not in all_data
        assert "models" not in sc.system_config._data

    def test_update_all_preserves_legacy_models_when_omitted(self, tmp_path, monkeypatch):
        """设置页 PUT 不含 models 时，磁盘上已有 legacy models 仍保留。"""
        from config_store import system_config as sc

        legacy = [{"id": "legacy-model-1", "name": "Legacy 1", "default": True}]
        cfg_path = tmp_path / "system_config.json"
        cfg_path.write_text(json.dumps({
            "system": {"port": 8765, "default_backend": "opencode"},
            "backends": {"opencode": {"enabled": True, "cli_path": ""}},
            "models": {"opencode": legacy},
        }), encoding="utf-8")
        monkeypatch.setattr(sc, "SYSTEM_CONFIG_FILE", cfg_path)
        sc.system_config._load()

        sc.system_config.update_all({
            "system": {"port": 8766, "default_backend": "opencode"},
            "backends": {"opencode": {"enabled": True, "cli_path": "/bin/opencode"}},
        })

        assert sc.system_config.get_all()["system"]["port"] == 8766
        assert sc.system_config.get_models("opencode") == legacy
        assert "models" not in sc.system_config.get_all()

    def test_other_fields_unaffected(self, tmp_path, monkeypatch):
        """剥离 models 不应影响 system/backends 字段。"""
        from config_store import system_config as sc

        cfg_path = tmp_path / "system_config.json"
        cfg_path.write_text(json.dumps({
            "system": {"port": 9999, "default_backend": "claude", "debug": True},
            "backends": {
                "opencode": {"enabled": True, "cli_path": "/usr/local/bin/opencode"},
                "claude": {"enabled": True, "cli_path": ""},
            },
            "models": {"opencode": [{"id": "test"}]},
        }), encoding="utf-8")
        monkeypatch.setattr(sc, "SYSTEM_CONFIG_FILE", cfg_path)
        sc.system_config._load()

        all_data = sc.system_config.get_all()
        assert all_data["system"]["port"] == 9999
        assert all_data["system"]["default_backend"] == "claude"
        assert all_data["system"]["debug"] is True
        assert all_data["backends"]["opencode"]["cli_path"] == "/usr/local/bin/opencode"
