"""Skill 功能模块 — 统一入口。

向后兼容: from common.skill_catalog import * 仍可通过 common/__init__.py re-export 工作。
"""
from common.skill.skill_catalog import *  # noqa: F401,F403
from common.skill.skill_categories import *  # noqa: F401,F403
from common.skill.skill_display_names import *  # noqa: F401,F403
from common.skill.skill_extract import *  # noqa: F401,F403
from common.skill.skill_groups import *  # noqa: F401,F403
from common.skill.skill_install import *  # noqa: F401,F403
from common.skill.skill_link import *  # noqa: F401,F403
from common.skill.skill_settings import *  # noqa: F401,F403

__all__ = [
    'skill_catalog', 'skill_categories', 'skill_display_names',
    'skill_extract', 'skill_groups', 'skill_install',
    'skill_link', 'skill_settings',
]
