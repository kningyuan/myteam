"""测试 agent_factory 核心函数。

generate_agent, _default_model。
使用 monkeypatch 替换路径和外部函数调用，不写生产目录。
"""

from unittest.mock import MagicMock

import base.agent_factory as af


class TestGenerateAgent:
    """generate_agent 创建 Agent 的功能。"""

    def test_generate_agent_creates_workspace(self, tmp_path, monkeypatch):
        """generate_agent 创建 workspace 目录和身份文件。"""
        ws_dir = tmp_path / "workspaces"
        ws_dir.mkdir(exist_ok=True)
        monkeypatch.setattr(af, "WORKSPACES_DIR", ws_dir)
        monkeypatch.setattr(af, "WORKSPACE_PREFIX", "workspace-")

        monkeypatch.setattr(af, "_default_model", lambda bid: "test-model")
        monkeypatch.setattr(af, "_generate_via_llm", lambda *a, **kw: None)
        monkeypatch.setattr(af, "set_agent_backend_config", lambda *a, **kw: None)
        monkeypatch.setattr(af, "register_agent", lambda *a, **kw: None)

        result = af.generate_agent(
            "testagent", "测试 Agent 描述",
            backend_id="opencode", model="m1",
            use_existing_agent_for_gen=False,
        )
        assert result["success"] is True
        assert result["agent_id"] == "testagent"

        werk = ws_dir / "workspace-testagent"
        assert werk.is_dir()
        assert (werk / "IDENTITY.md").exists()
        assert (werk / "AGENTS.md").exists()
        assert (werk / "SOUL.md").exists()
        assert (werk / "USER.md").exists()
        assert (werk / ".trigger").is_dir()
        assert (werk / ".response").is_dir()

    def test_generate_agent_with_chinese_name(self, tmp_path, monkeypatch):
        """指定 chinese_name 后身份文件包含该名称。"""
        ws_dir = tmp_path / "workspaces"
        ws_dir.mkdir(exist_ok=True)
        monkeypatch.setattr(af, "WORKSPACES_DIR", ws_dir)
        monkeypatch.setattr(af, "WORKSPACE_PREFIX", "workspace-")
        monkeypatch.setattr(af, "_default_model", lambda bid: "test-model")
        monkeypatch.setattr(af, "_generate_via_llm", lambda *a, **kw: None)
        monkeypatch.setattr(af, "set_agent_backend_config", lambda *a, **kw: None)
        monkeypatch.setattr(af, "register_agent", lambda *a, **kw: None)

        af.generate_agent(
            "agent_x", "测试", chinese_name="测试员",
            use_existing_agent_for_gen=False,
        )
        identity = (ws_dir / "workspace-agent_x" / "IDENTITY.md").read_text(encoding="utf-8")
        assert "测试员" in identity

    def test_generate_agent_existing_workspace(self, tmp_path, monkeypatch):
        """workspace 已存在时返回错误。"""
        ws_dir = tmp_path / "workspaces"
        ws_dir.mkdir(exist_ok=True)
        (ws_dir / "workspace-existing").mkdir()
        monkeypatch.setattr(af, "WORKSPACES_DIR", ws_dir)
        monkeypatch.setattr(af, "WORKSPACE_PREFIX", "workspace-")
        monkeypatch.setattr(af, "_default_model", lambda bid: "test-model")

        result = af.generate_agent(
            "existing", "已存在", use_existing_agent_for_gen=False,
        )
        assert result["success"] is False
        assert "工作目录已存在" in result.get("error", "")

    def test_generate_agent_creates_template_files(self, tmp_path, monkeypatch):
        """使用模板生成时所有 4 个身份文件都被创建。"""
        ws_dir = tmp_path / "workspaces"
        ws_dir.mkdir(exist_ok=True)
        monkeypatch.setattr(af, "WORKSPACES_DIR", ws_dir)
        monkeypatch.setattr(af, "WORKSPACE_PREFIX", "workspace-")
        monkeypatch.setattr(af, "_default_model", lambda bid: "test-model")
        monkeypatch.setattr(af, "set_agent_backend_config", lambda *a, **kw: None)
        monkeypatch.setattr(af, "register_agent", lambda *a, **kw: None)

        result = af.generate_agent(
            "newbie", "新手 Agent", use_existing_agent_for_gen=False,
        )
        assert set(result["files"]) == {"IDENTITY.md", "AGENTS.md", "SOUL.md", "USER.md"}


class TestDefaultModel:
    """_default_model 函数。"""

    def test_default_model_returns_model(self, monkeypatch):
        """_default_model 返回后端的默认模型。"""
        mock_adapter = MagicMock()
        mock_adapter.get_default_model.return_value = "default-model-id"
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter
        import adapter.core.registry as areg
        monkeypatch.setattr(areg, "registry", mock_registry)

        model = af._default_model("opencode")
        assert model == "default-model-id"

    def test_default_model_no_adapter_returns_empty(self, monkeypatch):
        """不知名的后端返回空字符串。"""
        mock_registry = MagicMock()
        mock_registry.get.return_value = None
        import adapter.core.registry as areg
        monkeypatch.setattr(areg, "registry", mock_registry)

        model = af._default_model("unknown")
        assert model == ""


class TestHelperFunctions:
    """辅助函数。"""

    def test_suggest_agent_id(self, tmp_path, monkeypatch):
        """suggest_agent_id 根据描述生成 id。"""
        ws_dir = tmp_path / "workspaces"
        ws_dir.mkdir(exist_ok=True)
        monkeypatch.setattr(af, "WORKSPACES_DIR", ws_dir)
        monkeypatch.setattr(af, "WORKSPACE_PREFIX", "workspace-")

        aid = af.suggest_agent_id("developer for frontend")
        assert aid == "developer"

    def test_suggest_agent_id_avoid_collision(self, tmp_path, monkeypatch):
        """id 冲突时自动编号。"""
        ws_dir = tmp_path / "workspaces"
        ws_dir.mkdir(exist_ok=True)
        (ws_dir / "workspace-developer").mkdir()
        monkeypatch.setattr(af, "WORKSPACES_DIR", ws_dir)
        monkeypatch.setattr(af, "WORKSPACE_PREFIX", "workspace-")

        aid = af.suggest_agent_id("developer backend")
        assert aid == "developer1"

    def test_list_available_agent_ids(self, tmp_path, monkeypatch):
        """list_available_agent_ids 列出已有 agent。"""
        ws_dir = tmp_path / "workspaces"
        ws_dir.mkdir(exist_ok=True)
        (ws_dir / "workspace-main").mkdir()
        (ws_dir / "workspace-product").mkdir()
        monkeypatch.setattr(af, "WORKSPACES_DIR", ws_dir)
        monkeypatch.setattr(af, "WORKSPACE_PREFIX", "workspace-")

        ids = af.list_available_agent_ids()
        assert ids == ["main", "product"]

    def test_extract_name_from_identity(self):
        """从 identity 内容提取 name。"""
        content = "name：小张\nrole: 开发"
        assert af._extract_name_from_identity(content) == "小张"

    def test_extract_name_from_identity_no_match(self):
        """没有匹配时返回空字符串。"""
        assert af._extract_name_from_identity("无匹配内容") == ""


class TestGenerateAgentWithLLMFallback:
    """LLM 生成失败时回退到模板。"""

    def test_llm_fallback_to_template(self, tmp_path, monkeypatch):
        """LLM 返回 None 时使用模板生成。"""
        ws_dir = tmp_path / "workspaces"
        ws_dir.mkdir(exist_ok=True)
        monkeypatch.setattr(af, "WORKSPACES_DIR", ws_dir)
        monkeypatch.setattr(af, "WORKSPACE_PREFIX", "workspace-")
        monkeypatch.setattr(af, "_default_model", lambda bid: "test-model")
        monkeypatch.setattr(af, "_generate_via_llm", lambda *a, **kw: None)
        monkeypatch.setattr(af, "set_agent_backend_config", lambda *a, **kw: None)
        monkeypatch.setattr(af, "register_agent", lambda *a, **kw: None)

        result = af.generate_agent("fallback", "测试回退")
        assert result["success"] is True
        assert "IDENTITY.md" in result["files"]