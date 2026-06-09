# R-K6 设置 Tab — budget 降级字段 — 实现说明

| 字段 | 内容 |
|------|------|
| 需求 ID | R-K6（UI 补全） |
| 状态 | ✅ 已完成 |
| 日期 | 2026-06-09 |

## 交叉评审共识

| 角色 | 裁决 |
|------|------|
| 架构师 | 写入 `skill_config.process_defaults`，经既有 `kernel_configs_for_run` → `ProcessConfig`；不新增 API |
| QA | 保存后 `budget_degrade_threshold/backend/model` 落盘；内核行为仍由 `reg_b_budget_degrade.py` 验证 |
| 工程 | 设置 Tab「高级」区三字段：阈值%、降级 backend、降级 model |

## 验收

- [x] `frontend/index.html` 三控件
- [x] `frontend/settings.js` load/save + 模型列表联动
- [x] `kernel_config.process_from_defaults` 已支持（`test_process_from_defaults_l3_budget`）

## 改动文件

- `frontend/index.html`
- `frontend/settings.js`
- `frontend/ui-core.js`（DOM 注册）

## 手动验证

1. 打开 Hub → 设置 → 协作引擎 → 高级
2. 设置预算降级阈值 75%、backend=opencode、model=某低成本模型 → 保存
3. 检查 `config/skill_config.json` 中 `process_defaults.budget_degrade_*` 已更新
