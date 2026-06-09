# R-C9 Skill Config API — 实现说明

| 字段 | 内容 |
|------|------|
| 需求 ID | R-C9 |
| 状态 | ✅ 已完成 |
| 日期 | 2026-06-09 |

## 交叉评审共识

| 角色 | 裁决 |
|------|------|
| 架构师 | `skill_config.json` 仍是配置真相源；API 只做读写与缓存失效，不引入新配置层 |
| QA | 同时锁定 `/api/skill-config`（现有前端）与 `/api/skill_config`（需求文档）两条路径 |
| 工程 | 复用同一 handler；PUT 后调用 `reload_skill_settings()`，确保无需重启 |

## 验收

- [x] GET `/api/skill-config`
- [x] GET `/api/skill_config`
- [x] PUT `/api/skill_config` 更新配置并触发 `reload_skill_settings()`
- [x] `test_skill_config_api.py` PASS
- [x] `reg_c9_skill_config_api.py` PASS

## 改动文件

- `backend/hub/api/server.py`
- `backend/common/tests/test_skill_config_api.py`
- `scripts/regression/reg_c9_skill_config_api.py`
- `scripts/regression/run_regression.sh`

## 回归

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/tests/test_skill_config_api.py -q
MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend venv/bin/python3 scripts/regression/reg_c9_skill_config_api.py
./scripts/regression/run_regression.sh --suite framework
```
