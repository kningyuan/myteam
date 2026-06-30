"""Agent 身份识别测试 — AgentIdentityBuilder / MultiAgentManager。

用 tmp_path（经 conftest 的 make_workspace 工厂）建假 workspace，
覆盖：读取 IDENTITY.md 提取中文名/角色、get_identity_context 拼装、
get_agent_prompt_prefix、extract_chinese_name 兜底映射、
MultiAgentManager.build_multi_agent_context。
"""
from __future__ import annotations

from base.agent_identity import AgentIdentityBuilder, MultiAgentManager


# ============ AgentIdentityBuilder：读取身份文件 ============

def test_read_identity_extracts_name_and_role(make_workspace):
    ws = make_workspace(
        "alice",
        identity="# 身份\n名字: 爱丽丝\n角色: 测试工程师\n",
        soul="# 灵魂\n严谨客观\n",
    )
    b = AgentIdentityBuilder("alice", str(ws))
    assert b.chinese_name == "爱丽丝"
    assert b.agent_role == "测试工程师"
    # IDENTITY.md 与 SOUL.md 都被读入
    joined = "\n".join(b.identity_content)
    assert "# IDENTITY.md" in joined
    assert "# SOUL.md" in joined


def test_identity_context_assembles_block(make_workspace):
    ws = make_workspace("bob", identity="名字: 鲍勃\n角色: 架构师\n", soul="稳\n")
    b = AgentIdentityBuilder("bob", str(ws))
    ctx = b.get_identity_context()
    assert "Agent 身份信息" in ctx
    assert "鲍勃" in ctx
    assert "架构师" in ctx
    assert "# SOUL.md" in ctx


def test_identity_context_empty_when_no_files(tmp_path):
    b = AgentIdentityBuilder("ghost", str(tmp_path / "nope"))
    assert b.get_identity_context() == ""
    assert b.chinese_name is None
    assert b.agent_role is None


def test_prompt_prefix_uses_name_and_role(make_workspace):
    ws = make_workspace("carol", identity="名字: 卡罗尔\n角色: 产品经理\n")
    b = AgentIdentityBuilder("carol", str(ws))
    assert b.get_agent_prompt_prefix() == "【卡罗尔】产品经理\n"


def test_prompt_prefix_defaults_role_when_missing(make_workspace):
    ws = make_workspace("dan", identity="名字: 丹尼\n")
    b = AgentIdentityBuilder("dan", str(ws))
    # 角色缺失时兜底为 "AI 助手"
    assert b.get_agent_prompt_prefix() == "【丹尼】AI 助手\n"


# ============ extract_chinese_name：兜底映射 ============

def test_fallback_name_coordinator(tmp_path):
    # main → 项目协调专家（get_coordinator_id 已被 conftest 固定为 "main"）
    b = AgentIdentityBuilder("main", str(tmp_path / "x"))
    assert b.extract_chinese_name() == "项目协调专家"


def test_fallback_name_known_roles(tmp_path):
    assert AgentIdentityBuilder("product", str(tmp_path / "x")).extract_chinese_name() == "产品经理"
    assert AgentIdentityBuilder("research", str(tmp_path / "x")).extract_chinese_name() == "研究员"
    assert AgentIdentityBuilder("developer", str(tmp_path / "x")).extract_chinese_name() == "开发工程师"
    # 旧名 researcher 仍兜底为研究员
    assert AgentIdentityBuilder("researcher", str(tmp_path / "x")).extract_chinese_name() == "研究员"


def test_fallback_name_unknown_agent(tmp_path):
    b = AgentIdentityBuilder("nobody", str(tmp_path / "x"))
    assert b.extract_chinese_name() == "Agent-nobody"


def test_explicit_name_overrides_fallback(make_workspace):
    # IDENTITY.md 里读到名字时，不走兜底映射
    ws = make_workspace("product", identity="名字: 自定义产品名\n")
    b = AgentIdentityBuilder("product", str(ws))
    assert b.extract_chinese_name() == "自定义产品名"


# ============ MultiAgentManager：多 agent 上下文 ============

def test_multi_agent_manager_loads_workspaces(make_workspace):
    make_workspace("alice", identity="名字: 爱丽丝\n角色: 测试\n")
    make_workspace("bob", identity="名字: 鲍勃\n角色: 架构\n")
    mgr = MultiAgentManager()  # 读取已被 conftest patch 的 WORKSPACES_DIR
    assert set(mgr.agents.keys()) == {"alice", "bob"}
    info = mgr.get_all_agents_info()
    assert info["alice"]["name"] == "爱丽丝"
    assert info["bob"]["role"] == "架构"


def test_build_multi_agent_context_lists_others(make_workspace):
    make_workspace("alice", identity="名字: 爱丽丝\n角色: 测试\n")
    make_workspace("bob", identity="名字: 鲍勃\n角色: 架构\n")
    mgr = MultiAgentManager()
    ctx = mgr.build_multi_agent_context("alice")
    assert "协作团队" in ctx
    assert "鲍勃" in ctx and "bob" in ctx
    # 不包含当前 agent
    assert "爱丽丝" not in ctx


def test_build_multi_agent_context_empty_for_unknown(make_workspace):
    make_workspace("alice", identity="名字: 爱丽丝\n")
    mgr = MultiAgentManager()
    # 当前 agent 不在加载列表中 → 空串
    assert mgr.build_multi_agent_context("unknown") == ""


def test_build_multi_agent_context_empty_when_solo(make_workspace):
    make_workspace("solo", identity="名字: 独行侠\n角色: 孤狼\n")
    mgr = MultiAgentManager()
    # 仅自己一个 agent，无协作对象 → 空串
    assert mgr.build_multi_agent_context("solo") == ""


def test_multi_agent_manager_get_agent(make_workspace):
    make_workspace("alice", identity="名字: 爱丽丝\n")
    mgr = MultiAgentManager()
    assert mgr.get_agent("alice") is not None
    assert mgr.get_agent("nobody") is None
