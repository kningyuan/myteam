"""conftest — base/ 模块测试的隔离环境。

参照 ``backend/common/roundtable/tests/conftest.py`` 的风格（确保 backend/ 在
sys.path），并补充两类隔离 fixture：

1. ``isolated_paths``（autouse）—— 用 tmp_path 重定向 ``common.paths`` 的路径常量
   （WORKSPACES_DIR / AGENTS_CONFIG_FILE / GROUPS_FILE / GROUP_ARCHIVES_FILE 等）。
   关键点：base 各子模块在 ``from common.paths import XXX`` 时已把常量**按名绑定**到
   自身命名空间，仅 patch ``common.paths`` 不够，必须逐一 patch 各 base 子模块的绑定。

2. ``mock_stream_chat``（autouse）—— mock 掉 ``stream_chat``（委托 hub.services，需
   Hub 运行），并 stub ``system_config``（避免读写真实 config/system_config.json）。

绝不写真实 config/ 或 business/；不依赖外部 CLI、不依赖 Hub 服务器运行。
"""
import sys
from pathlib import Path

# 确保 backend/ 在 sys.path（子目录深度变化后幂等注入）
_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import pytest  # noqa: E402


class _StubSystemConfig:
    """轻量 system_config 替身——避免读写真实 config/system_config.json。

    仅实现 base.agent_chat._derive_backend_config 用到的两个方法：
    ``get(*keys, default=)`` 与 ``get_default_model(backend_id)``。
    """

    def __init__(self):
        self._data = {
            "system": {"default_backend": "opencode", "coordinator_agent_id": "main"},
            "backends": {
                "opencode": {"models": [{"id": "stub-model", "default": True}]},
            },
        }

    def get(self, *keys, default=None):
        val = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
                if val is None:
                    return default
            else:
                return default
        return val

    def get_default_model(self, backend_id="opencode"):
        models = self.get("backends", backend_id, "models", default=[]) or []
        for m in models:
            if m.get("default"):
                return m["id"]
        return self.get("system", "default_model", default="stub-model")


def _empty_stream(*args, **kwargs):
    """stream_chat 替身：返回空生成器，确保测试不会触达真实 Hub/CLI。"""
    return iter(())


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    """把所有路径常量重定向到 tmp_path，绝不写真实 config/ 或 business/。"""
    workspaces = tmp_path / "workspaces"
    workspaces.mkdir()
    business = tmp_path / "business"
    business_config = business / "config"
    business_config.mkdir(parents=True)
    tasks_dir = business / "tasks"

    agents_config = business_config / "agents_config.json"
    agents_registry = business_config / "agents_registry.json"
    groups_file = business_config / "groups.json"
    group_archives = business_config / "group_archives.json"

    # 1) common.paths 模块全局
    #    to_relative_path / resolve_path / resolve_workspace 是函数，运行时读这里的
    #    模块全局（MYTEAM_ROOT / WORKSPACES_DIR），patch common.paths 即生效。
    import common.paths as p
    monkeypatch.setattr(p, "MYTEAM_ROOT", tmp_path)
    monkeypatch.setattr(p, "BUSINESS_DIR", business)
    monkeypatch.setattr(p, "BUSINESS_CONFIG_DIR", business_config)
    monkeypatch.setattr(p, "WORKSPACES_DIR", workspaces)
    monkeypatch.setattr(p, "AGENTS_CONFIG_FILE", agents_config)
    monkeypatch.setattr(p, "AGENTS_REGISTRY_FILE", agents_registry)
    monkeypatch.setattr(p, "GROUPS_FILE", groups_file)
    monkeypatch.setattr(p, "GROUP_ARCHIVES_FILE", group_archives)
    monkeypatch.setattr(p, "TASKS_DIR", tasks_dir)

    # 2) base 各子模块按名绑定的常量（import 时已拷贝引用，须逐一 patch）
    import base.agent_identity as ai
    monkeypatch.setattr(ai, "WORKSPACES_DIR", workspaces)
    # extract_chinese_name 兜底映射用 get_coordinator_id()，固定为 "main" 以可断言
    monkeypatch.setattr(ai, "get_coordinator_id", lambda: "main")

    import base.agent_chat as ac
    monkeypatch.setattr(ac, "WORKSPACES_DIR", workspaces)
    monkeypatch.setattr(ac, "AGENTS_CONFIG_FILE", agents_config)
    monkeypatch.setattr(ac, "AGENTS_REGISTRY_FILE", agents_registry)
    monkeypatch.setattr(ac, "GROUPS_FILE", groups_file)
    monkeypatch.setattr(ac, "system_config", _StubSystemConfig())

    import base.group_manager as gm
    monkeypatch.setattr(gm, "GROUPS_FILE", groups_file)
    monkeypatch.setattr(gm, "TASKS_DIR", tasks_dir)

    return tmp_path


@pytest.fixture(autouse=True)
def mock_stream_chat(monkeypatch):
    """mock stream_chat（base.agent_chat 定义；group_manager 按名绑定）——不依赖 Hub/CLI。"""
    import base.agent_chat as ac
    import base.group_manager as gm
    monkeypatch.setattr(ac, "stream_chat", _empty_stream)
    monkeypatch.setattr(gm, "stream_chat", _empty_stream)


@pytest.fixture
def make_workspace(tmp_path):
    """工厂：在 tmp workspaces 下建一个带身份文件的假 workspace。

    读取 ai.WORKSPACES_DIR（已被 isolated_paths patch 到 tmp_path）。
    """
    import base.agent_identity as ai

    def _make(agent_id: str, identity: str = "", soul: str = "", user: str = "") -> Path:
        ws = ai.WORKSPACES_DIR / f"workspace-{agent_id}"
        ws.mkdir(parents=True, exist_ok=True)
        if identity:
            (ws / "IDENTITY.md").write_text(identity, encoding="utf-8")
        if soul:
            (ws / "SOUL.md").write_text(soul, encoding="utf-8")
        if user:
            (ws / "USER.md").write_text(user, encoding="utf-8")
        return ws

    return _make
