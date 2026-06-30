"""backend 顶层 conftest — 跨子模块的测试隔离。

隔离 agents_registry.json：默认指向不存在的临时路径（空注册表），
避免运行时产物（business/config/agents_registry.json）污染单测。
测试若需自定义注册表，monkeypatch paths.AGENTS_REGISTRY_FILE 或
agent_registry.REGISTRY_FILE 即可覆盖。
"""
import pytest


@pytest.fixture(autouse=True)
def _isolate_agents_registry(monkeypatch, tmp_path):
    """默认隔离 agents_registry.json：空注册表，防运行时产物污染。"""
    from common import paths
    empty = tmp_path / "_empty_agents_registry.json"  # 不创建 → _load_registry 返回空
    monkeypatch.setattr(paths, "AGENTS_REGISTRY_FILE", empty)
    monkeypatch.setattr("common.agent.agent_registry.REGISTRY_FILE", empty)
    # agent_id_policy 的 _registry_agent_ids 有 lru_cache，清缓存防跨测例污染
    try:
        from common.agent.agent_id_policy import invalidate_agent_id_policy_cache
        invalidate_agent_id_policy_cache()
    except Exception:
        pass
