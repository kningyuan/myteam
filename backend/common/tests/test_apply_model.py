import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import base.agent_chat as ac  # noqa: E402


def test_apply_model_only_same_backend_and_preserves_fields(monkeypatch):
    """批量应用只改同后端 agent，且保留 name/workspace/extra。"""
    store = {
        "alice": {"backend": "opencode", "model": "old-a", "name": "爱丽丝", "workspace": "/ws/alice"},
        "bob": {"backend": "opencode", "model": "old-b", "extra": {"k": "v"}},
        "carol": {"backend": "claude", "model": "old-c", "name": "卡罗尔"},
    }
    agents = [
        {"id": "alice", "backend": "opencode"},
        {"id": "bob", "backend": "opencode"},
        {"id": "carol", "backend": "claude"},
    ]

    monkeypatch.setattr(ac, "scan_agents", lambda: agents)
    monkeypatch.setattr(ac, "_load_agents_config", lambda: dict(store))
    monkeypatch.setattr(ac, "_save_agents_config", lambda cfg: store.update(cfg))

    result = ac.apply_model_to_all("opencode", "new-model")

    assert set(result["applied"]) == {"alice", "bob"}
    assert result["skipped"] == ["carol"]
    assert store["alice"]["model"] == "new-model"
    assert store["bob"]["model"] == "new-model"
    assert store["carol"]["model"] == "old-c"  # 别的后端不动

    # 保留原有字段
    assert store["alice"]["name"] == "爱丽丝"
    assert store["alice"]["workspace"] == "/ws/alice"
    assert store["bob"]["extra"] == {"k": "v"}
