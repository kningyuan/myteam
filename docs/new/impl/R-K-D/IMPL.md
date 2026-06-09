# R-K-D 设置贯通 — 实现说明（示范）

| 字段 | 内容 |
|------|------|
| 需求 ID | R-K-D（对应 R-S3 / R-U4） |
| 状态 | ✅ 已完成 |
| 日期 | 2026-06-09 |

## 背景

设置 Tab 写入的 `skill_config.process_defaults` 必须在 **Hub 新建项目、CLI run_kernel、resume 续跑** 三条路径上生效同一套 `ProcessConfig` + `WatchdogConfig`。

## 验收

- [x] `kernel_configs_for_run()` 统一构建双配置
- [x] `resume_project` 不再使用裸 `ProcessConfig()`
- [x] `_resume_kernel_bg` 传入 defaults
- [x] `update_skill_config_api` 后 `reload_skill_settings()`
- [x] `reg_d_config_linkage.py` PASS

## 改动文件

- `backend/common/kernel_config.py`
- `backend/common/run_kernel.py`
- `backend/hub/api/server.py`
- `backend/common/tests/test_kernel_config.py`

## 回归

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/tests/test_kernel_config.py -q
MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend python3 scripts/regression/reg_d_config_linkage.py
```
