"""config_store 测试公共 fixture。

隔离策略：把三个配置文件路径重定向到 ``tmp_path``，重新实例化各存储类，
**绝不写真实 ``config/`` 目录**。参照 ``backend/common/tests/test_fix_be_contract.py``
的 ``monkeypatch`` + 重新加载风格。

注意：``system_config.py`` / ``skill_config.py`` 顶部用
``from common.paths import XXX_FILE`` 把路径常量绑定到了**自身模块全局**，
故 ``common.paths`` 与子模块两处都要 patch，方法体内引用的才是新路径。
``sessions.py`` 的 ``SessionStore.__init__`` 默认参数 ``path=SESSION_MAP_FILE``
在模块导入时已求值绑定，patch 模块全局对默认参数无效——因此必须**显式传 ``path=``**。
"""
import sys
from pathlib import Path

import pytest

# 确保 backend/ 在 sys.path（子目录深度变化后幂等注入）
_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── SystemConfig ──


@pytest.fixture
def sys_cfg_path(tmp_path, monkeypatch):
    """重定向 SYSTEM_CONFIG_FILE 到 tmp_path，返回目标路径。"""
    from common import paths as paths_mod
    from config_store import system_config as sc_mod

    target = tmp_path / "system_config.json"
    monkeypatch.setattr(paths_mod, "SYSTEM_CONFIG_FILE", target)
    monkeypatch.setattr(sc_mod, "SYSTEM_CONFIG_FILE", target)
    return target


@pytest.fixture
def sys_cfg(sys_cfg_path):
    """返回一个隔离的 SystemConfig 实例（指向 tmp_path，文件不存在时落盘 DEFAULT_CONFIG）。"""
    from config_store.system_config import SystemConfig

    return SystemConfig()


# ── SkillConfig ──


@pytest.fixture
def skill_cfg_path(tmp_path, monkeypatch):
    """重定向 SKILL_CONFIG_FILE 到 tmp_path，返回目标路径。"""
    from common import paths as paths_mod
    from config_store import skill_config as sk_mod

    target = tmp_path / "skill_config.json"
    monkeypatch.setattr(paths_mod, "SKILL_CONFIG_FILE", target)
    monkeypatch.setattr(sk_mod, "SKILL_CONFIG_FILE", target)
    return target


@pytest.fixture
def skill_cfg(skill_cfg_path):
    """返回一个隔离的 SkillConfig 实例（指向 tmp_path）。"""
    from config_store.skill_config import SkillConfig

    return SkillConfig()


# ── SessionStore ──


@pytest.fixture
def session_store(tmp_path, monkeypatch):
    """返回一个隔离的 SessionStore 实例（文件指向 tmp_path）。

    显式传 ``path=`` 隔离（见模块 docstring 说明）；同时 patch
    ``common.paths.SESSION_MAP_FILE`` 以满足“路径常量重定向”的语义一致性。
    """
    from common import paths as paths_mod
    from config_store.sessions import SessionStore

    target = tmp_path / "session_map.json"
    monkeypatch.setattr(paths_mod, "SESSION_MAP_FILE", target)
    return SessionStore(path=target)
