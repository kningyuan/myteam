# Skill 模块

Skill 库扫描与目录管理。从 business/skills/ 扫描 SKILL.md,提供分类/显示名/安装/链接。

## 核心文件

- `skill_catalog.py` — Skill 目录扫描(单一出处)
- `skill_categories.py` — Skill 分类
- `skill_display_names.py` — Skill 显示名
- `skill_extract.py` — Skill 抽取(从交付物)
- `skill_groups.py` — Skill 分组
- `skill_install.py` — Skill 安装
- `skill_link.py` — Skill 链接
- `skill_settings.py` — Skill 设置

## 依赖关系

依赖:common/paths。被依赖:hub/api/skills_api, common/agent/agent_skills

## 测试

测试位于 `common/skill/tests/`,运行:

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/skill/tests/ -q
```

测试清单(与 `tests/` 目录实际文件一一对应,功能变更后同步更新):

- `test_skill_catalog.py`
- `test_skill_categories.py`
- `test_skill_config_25_field.py`
- `test_skill_config_api.py`
- `test_skill_display_names.py`
- `test_skill_extract.py`
- `test_skill_groups.py`
- `test_skill_link.py`
- `test_skill_mount_repair.py`
- `test_skills_api.py`

## 变更维护

- 新增/删除文件时,更新本 README 的「核心文件」清单
- 新增/删除测试时,重跑 `python3 _gen_readme.py` 同步「测试清单」
- 重命名模块时,同步更新依赖方的 import 路径