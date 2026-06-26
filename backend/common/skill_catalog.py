# Backward-compatible stub: delegates to the skill/ package.
# Original file was moved to common/skill/skill_catalog.py.
from common.skill.skill_catalog import *  # noqa: F401,F403
try:
    from common.skill.skill_catalog import __all__ as _stub_all
    __all__ = list(_stub_all)
except ImportError:
    __all__ = []
