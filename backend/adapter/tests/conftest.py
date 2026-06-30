"""conftest — 确保 backend/ 在 sys.path(子目录深度变化后幂等注入)。"""
import sys
from pathlib import Path
_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
