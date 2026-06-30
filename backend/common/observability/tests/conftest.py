"""conftest — 确保 backend/ 在 sys.path(子目录深度变化后幂等注入)。"""
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


@pytest.fixture(autouse=True)
def _inject_dispatch_token(monkeypatch):
    """测试无子进程，按 interaction_id 动态注入 MYTEAM_DISPATCH_TOKEN。"""
    from common.delivery import submit_result as _sr
    _real = _sr._verify_dispatch_gate

    def _patched(response, response_path):
        iid = str(response.get("interaction_id") or "").strip()
        if iid:
            monkeypatch.setenv(_sr.DISPATCH_TOKEN_ENV, iid)
        return _real(response, response_path)

    monkeypatch.setattr(_sr, "_verify_dispatch_gate", _patched)
