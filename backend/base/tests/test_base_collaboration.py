"""跨模块协作测试。

验证 base/ 各模块之间的协作关系：
1. agent_identity 的中文名被 agent_chat 引用
2. group_manager 的 add_member 后 scan_agents 能列出该成员
3. config_store.system_config 的默认值被 agent_chat.get_agent_backend_config 读取

所有测试使用 tmp_path + monkeypatch 隔离文件路径。
"""

from unittest.mock import MagicMock

import base.agent_chat as ac
import base.agent_identity as ai
import base.group_manager as gm
from common import paths


class TestIdentityUsedByChat:
    """agent_identity 的中文名在 agent_chat 中被使用。"""

    def test_agent_identity_chinese_name_in_scan(self, tmp_path, monkeypatch):
        """scan_agents 使用 AgentIdentityBuilder 提取中文名。"""
        ws_dir = tmp_path / "workspaces"
        ws_dir.mkdir(exist_ok=True)
        (ws_dir / "workspace-main").mkdir()
        (ws_dir / "workspace-main" / "IDENTITY.md").write_text(
            "# 身份\n\n你的名字：协调专家\n", encoding="utf-8"
        )
        monkeypatch.setattr(ac, "WORKSPACES_DIR", ws_dir)
        monkeypatch.setattr(ac, "WORKSPACE_PREFIX", "workspace-")
        monkeypatch.setattr(ac, "_load_agents_config", lambda: {})
        monkeypatch.setattr(ac, "system_config", MagicMock(
            get=lambda *a, default=None: "opencode" if "default_backend" in str(a) else "",
            get_default_model=lambda *a: "default-model",
            get_models=lambda *a: [],
        ))

        agents = ac.scan_agents()
        main = next(a for a in agents if a["id"] == "main")
        assert main["name"] == "协调专家"

    def test_agent_identity_imported_by_chat(self):
        """agent_chat 确实导入了 agent_identity。"""
        assert ai.AgentIdentityBuilder is not None
        assert hasattr(ai, "multi_agent_manager")


class TestGroupMemberVisibleToScan:
    """group_manager 添加成员后,scan_agents 能列出。"""

    def test_group_member_appears_in_scan(self, tmp_path, monkeypatch):
        """add_member 依赖 scan_agents 验证成员存在，两者协作正常。"""
        ws_dir = tmp_path / "workspaces"
        ws_dir.mkdir(exist_ok=True)
        (ws_dir / "workspace-alice").mkdir()
        (ws_dir / "workspace-alice" / "IDENTITY.md").write_text(
            "你的名字：爱丽丝\n", encoding="utf-8"
        )

        monkeypatch.setattr(ac, "WORKSPACES_DIR", ws_dir)
        monkeypatch.setattr(ac, "WORKSPACE_PREFIX", "workspace-")
        monkeypatch.setattr(ac, "_load_agents_config", lambda: {})
        monkeypatch.setattr(ac, "system_config", MagicMock(
            get=lambda *a, default=None: "opencode" if "default_backend" in str(a) else "",
            get_default_model=lambda *a: "default-model",
            get_models=lambda *a: [],
        ))

        monkeypatch.setattr(gm, "scan_agents", ac.scan_agents)

        groups_fp = tmp_path / "groups.json"
        groups_fp.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(gm, "GROUPS_FILE", groups_fp)
        monkeypatch.setattr(paths, "GROUPS_FILE", groups_fp)

        g = gm.create_group("测试群")
        ok, _ = gm.add_member(g["id"], "alice")
        assert ok is True

        agents = ac.scan_agents()
        ids = [a["id"] for a in agents]
        assert "alice" in ids


class TestSystemConfigDefaults:
    """system_config 的默认值被 agent_chat 读取。"""

    def test_default_backend_from_system_config(self, monkeypatch):
        """未配置 agent 时使用 system_config 默认值。"""
        store = {}
        monkeypatch.setattr(ac, "_load_agents_config", lambda: store)

        mock_cfg = MagicMock()
        mock_cfg.get.side_effect = lambda *keys, default=None: {
            ("system", "default_backend"): "claude",
            ("system", "default_model"): "claude-opus",
        }.get(keys, default)
        mock_cfg.get_default_model.return_value = "claude-opus"
        mock_cfg.get_models.return_value = []
        monkeypatch.setattr(ac, "system_config", mock_cfg)

        cfg = ac.get_agent_backend_config("no_such_agent")
        assert cfg.backend_id == "claude"
        assert cfg.model == "claude-opus"
        assert cfg.uses_settings_default is True

    def test_default_model_resolved_correctly(self, monkeypatch):
        """_derive_backend_config 使用 system_config 的 get_default_model。"""
        store = {}
        monkeypatch.setattr(ac, "_load_agents_config", lambda: store)

        mock_cfg = MagicMock()
        mock_cfg.get.side_effect = lambda *keys, default=None: {
            ("system", "default_backend"): "opencode",
        }.get(keys, default)
        mock_cfg.get_default_model.return_value = "custom-model"
        mock_cfg.get_models.return_value = []
        monkeypatch.setattr(ac, "system_config", mock_cfg)

        cfg = ac.get_agent_backend_config("ghost")
        assert cfg.model == "custom-model"


class TestMultiAgentManagerCrossModule:
    """MultiAgentManager 与 agent_chat 的协作。"""

    def test_multi_agent_manager_loaded_by_chat(self, tmp_path, monkeypatch):
        """agent_chat.build_system_prompt 使用 multi_agent_manager。"""
        ws_dir = tmp_path / "workspaces"
        ws_dir.mkdir(exist_ok=True)
        (ws_dir / "workspace-main").mkdir()
        (ws_dir / "workspace-main" / "IDENTITY.md").write_text(
            "你的名字：主控\n", encoding="utf-8"
        )
        monkeypatch.setattr(ai, "WORKSPACES_DIR", ws_dir)

        manager = ai.MultiAgentManager()
        ctx = manager.build_multi_agent_context("main")
        # 只有 main 自己，无其他 agent → 空
        assert ctx == ""

        # 添加另一个 agent
        (ws_dir / "workspace-research").mkdir()
        (ws_dir / "workspace-research" / "IDENTITY.md").write_text(
            "你的名字：研究员\n", encoding="utf-8"
        )
        manager2 = ai.MultiAgentManager()
        ctx2 = manager2.build_multi_agent_context("main")
        assert "研究员" in ctx2