"""SkillConfig 测试。

覆盖：
- DEFAULT_SKILL_CONFIG 默认值补齐（deep_merge，含损坏文件回退）
- get(*keys, default) 多级键查询（含 None 值视同缺失）
- get_all（直接返回内部引用，不剥离任何字段）
- update_all（替换语义 + 落盘）
"""
from __future__ import annotations

import json


from config_store.skill_config import DEFAULT_SKILL_CONFIG, SkillConfig


# ── DEFAULT_SKILL_CONFIG 默认值补齐（deep_merge） ──


class TestDefaultMerge:
    def test_default_skill_config_top_level_keys(self):
        assert set(DEFAULT_SKILL_CONFIG) == {
            "notifications", "hub", "executor", "auto_group",
            "process_defaults", "group_discussion",
        }

    def test_fresh_load_fills_defaults_and_persists(self, skill_cfg_path):
        """文件不存在时，_load 写出 DEFAULT_SKILL_CONFIG 并补齐全部默认值。"""
        assert not skill_cfg_path.exists()
        cfg = SkillConfig()

        assert skill_cfg_path.exists()
        assert cfg.get("notifications", "enable_telegram") is False
        assert cfg.get("notifications", "use_project_group") is True
        assert cfg.get("hub", "url") == "http://127.0.0.1:8765"
        assert cfg.get("executor", "poll_interval") == 5
        assert cfg.get("executor", "ack_timeout") == 300
        assert cfg.get("executor", "task_timeout") == 3600
        assert cfg.get("executor", "max_retries") == 3
        assert cfg.get("auto_group", "enabled") is True
        assert cfg.get("auto_group", "include_main") is True
        assert cfg.get("process_defaults", "default_project_budget") == 1000000
        assert cfg.get("process_defaults", "max_parallel") == 3
        assert cfg.get("process_defaults", "max_cycles") == 3
        assert cfg.get("group_discussion", "default_max_rounds") == 3
        assert cfg.get("group_discussion", "quorum_ratio") == 0.667
        assert cfg.get("group_discussion", "terminate_commands") == [
            "/终止讨论", "/终止圆桌", "/stop roundtable",
        ]

    def test_existing_file_loaded_as_is_without_merging_defaults(self, skill_cfg_path):
        """已存在的配置文件**原样加载**，缺失键不从 DEFAULT_SKILL_CONFIG 补齐。

        _load 仅在文件缺失/损坏/空时才 deep_merge DEFAULT_SKILL_CONFIG；
        文件存在且有内容时直接采用文件内容，不做默认值补齐。
        """
        skill_cfg_path.parent.mkdir(parents=True, exist_ok=True)
        skill_cfg_path.write_text(json.dumps({
            "executor": {"max_retries": 9},
        }), encoding="utf-8")
        cfg = SkillConfig()

        assert cfg.get("executor", "max_retries") == 9  # 原样保留
        assert cfg.get("executor", "poll_interval") is None  # 不补齐嵌套
        assert cfg.get("hub") is None  # 整块不补齐

    def test_deep_merge_fills_missing_top_and_nested_keys(self, skill_cfg):
        """直接测 _deep_merge：缺失的顶层/嵌套键补齐，已有键保留（递归合并）。"""
        target = {"executor": {"max_retries": 9}}
        skill_cfg._deep_merge(target, DEFAULT_SKILL_CONFIG)
        # 已有值保留
        assert target["executor"]["max_retries"] == 9
        # 缺失嵌套键补齐
        assert target["executor"]["poll_interval"] == 5
        assert target["executor"]["ack_timeout"] == 300
        # 缺失顶层键补齐
        assert target["hub"]["url"] == "http://127.0.0.1:8765"
        assert target["group_discussion"]["default_max_rounds"] == 3

    def test_corrupt_file_falls_back_to_defaults(self, skill_cfg_path):
        """JSON 解析失败时回退到 DEFAULT_SKILL_CONFIG。"""
        skill_cfg_path.parent.mkdir(parents=True, exist_ok=True)
        skill_cfg_path.write_text("<<<not json>>>", encoding="utf-8")
        cfg = SkillConfig()
        assert cfg.get("executor", "max_retries") == 3
        assert cfg.get("hub", "url") == "http://127.0.0.1:8765"


# ── get(*keys, default) 多级键查询 ──


class TestGet:
    def test_get_multilevel(self, skill_cfg):
        assert skill_cfg.get("executor", "ack_timeout") == 300
        assert skill_cfg.get("process_defaults", "max_cycles") == 3
        assert skill_cfg.get("group_discussion", "quorum_ratio") == 0.667

    def test_get_missing_key_returns_default(self, skill_cfg):
        assert skill_cfg.get("executor", "nope") is None
        assert skill_cfg.get("executor", "nope", default=42) == 42
        assert skill_cfg.get("missing", "k", default="d") == "d"

    def test_get_returns_default_when_value_is_none(self, skill_cfg):
        """键存在但值为 None 时，get 视同缺失返回 default。"""
        skill_cfg._data["executor"]["ack_timeout"] = None
        assert skill_cfg.get("executor", "ack_timeout", default=999) == 999

    def test_get_all_returns_full_data(self, skill_cfg):
        """get_all 直接返回内部引用（与 SystemConfig 不同，不剥离任何字段）。"""
        all_data = skill_cfg.get_all()
        assert "notifications" in all_data
        assert "group_discussion" in all_data
        assert all_data is skill_cfg._data


# ── update_all ──


class TestUpdateAll:
    def test_update_all_replaces_data(self, skill_cfg):
        """update_all 为整体替换语义。"""
        skill_cfg.update_all({"notifications": {"enable_telegram": True}})
        assert skill_cfg.get("notifications", "enable_telegram") is True
        # 替换语义：其余顶层键被移除
        assert skill_cfg.get("hub", "url", default="gone") == "gone"

    def test_update_all_persists_to_disk(self, skill_cfg, skill_cfg_path):
        skill_cfg.update_all({"hub": {"url": "http://1.2.3.4:9999"}})
        on_disk = json.loads(skill_cfg_path.read_text(encoding="utf-8"))
        assert on_disk["hub"]["url"] == "http://1.2.3.4:9999"
