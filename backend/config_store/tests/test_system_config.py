"""SystemConfig 测试。

覆盖：
- DEFAULT_CONFIG 默认值补齐（deep_merge，含嵌套 dict 与损坏文件回退）
- get / get_all（get_all 剥离 models）
- update_all（替换语义 + models 字段保留/拒收）
- get_models / get_default_model（default 标记 → system.default_model 回退）
- get_cli_path（读 backends.<id>.cli_path）
"""
from __future__ import annotations

import json


from config_store.system_config import DEFAULT_CONFIG, SystemConfig


# ── DEFAULT_CONFIG 默认值补齐（deep_merge） ──


class TestDefaultMerge:
    def test_default_config_has_no_models_key(self):
        """DEFAULT_CONFIG 本身不含 models（models 由 /api/backends 管理）。"""
        assert "models" not in DEFAULT_CONFIG

    def test_fresh_load_fills_defaults_and_persists(self, sys_cfg_path):
        """文件不存在时，_load 写出 DEFAULT_CONFIG 并补齐全部默认值。"""
        assert not sys_cfg_path.exists()
        cfg = SystemConfig()

        assert sys_cfg_path.exists()  # 已落盘
        assert cfg.get("system", "port") == 8765
        assert cfg.get("system", "default_backend") == "opencode"
        assert cfg.get("system", "default_model") == "sensenova/sensenova-6.7-flash-lite"
        assert cfg.get("system", "coordinator_agent_id") == "main"
        assert cfg.get("system", "deputy_agent_id") == "deputy"
        assert cfg.get("backends", "opencode", "enabled") is True
        assert cfg.get("backends", "opencode", "cli_path") == ""
        assert cfg.get("backends", "claude", "enabled") is True

    def test_existing_file_loaded_as_is_without_merging_defaults(self, sys_cfg_path):
        """已存在的配置文件**原样加载**，缺失键不从 DEFAULT_CONFIG 补齐。

        _load 仅在文件缺失/损坏/空时才 deep_merge DEFAULT_CONFIG；
        文件存在且有内容时直接采用文件内容，不做默认值补齐。
        """
        sys_cfg_path.parent.mkdir(parents=True, exist_ok=True)
        sys_cfg_path.write_text(json.dumps({
            "system": {"port": 9999},
            "backends": {"opencode": {"enabled": True, "cli_path": ""}},
        }), encoding="utf-8")

        cfg = SystemConfig()
        # 已有值原样保留
        assert cfg.get("system", "port") == 9999
        # 缺失键不补齐（区别于 fresh-load 路径）
        assert cfg.get("system", "default_backend") is None
        assert cfg.get("system", "coordinator_agent_id") is None
        assert cfg.get("backends", "claude") is None

    def test_deep_merge_fills_missing_top_and_nested_keys(self, sys_cfg):
        """直接测 _deep_merge：缺失的顶层/嵌套键补齐，已有键保留（递归合并）。"""
        target = {
            "system": {
                "port": 9999,
                "rules": {"profile_filenames": {"interactive": "my-interactive.md"}},
            },
        }
        sys_cfg._deep_merge(target, DEFAULT_CONFIG)
        # 已有值保留
        assert target["system"]["port"] == 9999
        assert target["system"]["rules"]["profile_filenames"]["interactive"] == "my-interactive.md"
        # 缺失顶层键补齐
        assert target["backends"]["opencode"]["enabled"] is True
        assert target["system"]["default_backend"] == "opencode"
        # 缺失嵌套键补齐（递归）
        profiles = target["system"]["rules"]["profile_filenames"]
        assert profiles["discussion"] == "brainstorming-guide.md"
        assert profiles["workflow_execute"] == "worker-template.md"
        assert profiles["ethos"] == "ethos.md"

    def test_corrupt_file_falls_back_to_defaults(self, sys_cfg_path):
        """JSON 解析失败时回退到 DEFAULT_CONFIG。"""
        sys_cfg_path.parent.mkdir(parents=True, exist_ok=True)
        sys_cfg_path.write_text("{not valid json", encoding="utf-8")

        cfg = SystemConfig()
        assert cfg.get("system", "port") == 8765
        assert cfg.get("system", "default_backend") == "opencode"


# ── get / get_all ──


class TestGet:
    def test_get_multilevel(self, sys_cfg):
        assert sys_cfg.get("system", "port") == 8765
        assert sys_cfg.get("backends", "opencode", "cli_path") == ""

    def test_get_missing_key_returns_default(self, sys_cfg):
        assert sys_cfg.get("system", "nope") is None
        assert sys_cfg.get("system", "nope", default="fb") == "fb"
        assert sys_cfg.get("missing", "path", default="d") == "d"

    def test_get_all_excludes_models(self, sys_cfg):
        """get_all() 剥离 models 字段（模型列表由 /api/backends 管理）。"""
        sys_cfg._data["models"] = {"opencode": [{"id": "x"}]}
        all_data = sys_cfg.get_all()
        assert "models" not in all_data
        assert "system" in all_data
        assert "backends" in all_data

    def test_get_all_does_not_strip_models_from_internal(self, sys_cfg):
        """get_all() 只在返回值剥离 models，内部 _data 仍保留。"""
        sys_cfg._data["models"] = {"opencode": [{"id": "x"}]}
        all_data = sys_cfg.get_all()
        assert "models" not in all_data
        assert sys_cfg._data["models"] == {"opencode": [{"id": "x"}]}


# ── update_all + models 保留 ──


class TestUpdateAll:
    def test_update_all_replaces_system_fields(self, sys_cfg):
        sys_cfg.update_all({
            "system": {"port": 8080, "default_backend": "claude"},
            "backends": {"opencode": {"enabled": True, "cli_path": "/x"}},
        })
        assert sys_cfg.get("system", "port") == 8080
        assert sys_cfg.get("system", "default_backend") == "claude"

    def test_update_all_strips_models_from_incoming(self, sys_cfg):
        """update_all 拒收外部传入的 models（即便传入也会被丢弃，保留既有）。"""
        sys_cfg._data["models"] = {"opencode": [{"id": "keep"}]}
        sys_cfg.update_all({
            "system": {"port": 8765},
            "models": {"opencode": [{"id": "inject"}]},
        })
        assert sys_cfg._data["models"] == {"opencode": [{"id": "keep"}]}
        assert "models" not in sys_cfg.get_all()

    def test_update_all_preserves_models_when_omitted(self, sys_cfg_path):
        """设置页 PUT 不含 models 时，磁盘上已有 models 仍保留。"""
        sys_cfg_path.parent.mkdir(parents=True, exist_ok=True)
        legacy = [{"id": "legacy-1", "default": True}]
        sys_cfg_path.write_text(json.dumps({
            "system": {"port": 8765},
            "backends": {"opencode": {"enabled": True, "cli_path": ""}},
            "models": {"opencode": legacy},
        }), encoding="utf-8")
        cfg = SystemConfig()

        cfg.update_all({
            "system": {"port": 9000},
            "backends": {"opencode": {"enabled": True, "cli_path": "/bin/oc"}},
        })
        assert cfg.get_models("opencode") == legacy
        assert cfg.get("system", "port") == 9000

    def test_update_all_persists_to_disk(self, sys_cfg, sys_cfg_path):
        sys_cfg.update_all({"system": {"port": 7777}})
        on_disk = json.loads(sys_cfg_path.read_text(encoding="utf-8"))
        assert on_disk["system"]["port"] == 7777


# ── get_models / get_default_model ──


class TestModels:
    def test_get_models_empty_when_absent(self, sys_cfg):
        assert sys_cfg.get_models("opencode") == []
        assert sys_cfg.get_models("claude") == []

    def test_get_models_returns_list(self, sys_cfg):
        sys_cfg._data["models"] = {
            "opencode": [{"id": "a"}, {"id": "b"}],
            "claude": [{"id": "c"}],
        }
        assert [m["id"] for m in sys_cfg.get_models("opencode")] == ["a", "b"]
        assert sys_cfg.get_models("claude")[0]["id"] == "c"

    def test_get_default_model_from_default_flag(self, sys_cfg):
        """models 中带 default=True 的条目优先。"""
        sys_cfg._data["models"] = {"opencode": [
            {"id": "a"},
            {"id": "b", "default": True},
        ]}
        assert sys_cfg.get_default_model("opencode") == "b"

    def test_get_default_model_fallback_to_system_default(self, sys_cfg):
        """无 models 时回退到 system.default_model。"""
        assert sys_cfg.get_default_model("opencode") == "sensenova/sensenova-6.7-flash-lite"

    def test_get_default_model_empty_when_system_default_blank(self, sys_cfg_path):
        """system.default_model 显式为空且无 models 时返回空串。"""
        sys_cfg_path.parent.mkdir(parents=True, exist_ok=True)
        sys_cfg_path.write_text(json.dumps({
            "system": {"default_model": ""},
            "backends": {"opencode": {"enabled": True, "cli_path": ""}},
        }), encoding="utf-8")
        cfg = SystemConfig()
        assert cfg.get_default_model("opencode") == ""


# ── get_cli_path ──


class TestGetCliPath:
    def test_default_cli_path_empty(self, sys_cfg):
        assert sys_cfg.get_cli_path("opencode") == ""
        assert sys_cfg.get_cli_path("claude") == ""

    def test_get_cli_path_configured(self, sys_cfg):
        sys_cfg._data["backends"]["opencode"]["cli_path"] = "/usr/local/bin/opencode"
        assert sys_cfg.get_cli_path("opencode") == "/usr/local/bin/opencode"

    def test_get_cli_path_for_claude(self, sys_cfg):
        sys_cfg._data["backends"]["claude"]["cli_path"] = "/opt/claude"
        assert sys_cfg.get_cli_path("claude") == "/opt/claude"

    def test_get_cli_path_unknown_backend_returns_empty(self, sys_cfg):
        """未知 backend_id → get 链路返回 default=''（env 兜底在 adapter 层，不在此处）。"""
        assert sys_cfg.get_cli_path("nonexistent") == ""
