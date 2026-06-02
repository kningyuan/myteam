"""兼容层 — 统一使用 store.system_config。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from store.system_config import SystemConfig, system_config  # noqa: F401

__all__ = ["SystemConfig", "system_config"]
