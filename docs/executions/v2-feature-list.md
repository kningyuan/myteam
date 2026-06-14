# v2 功能补齐清单（P3.2 · stub）

> **状态**：未 fully implemented — 本文件为执行边界占位，供 P4 产品验收对照。  
> **参照**：`docs/assessments/v1-v2-feature-matrix.md`、`docs/plans/`（P2.2 迁移方案，若存在）

## 范围说明

P3.2 在 Workflow v3 中定义为 **执行 stub**：由 developer 交付协调说明，不预设 UI 已全部补齐。实际 frontend-v2 工作可另开 frontend 任务。

## P0 链路（待标注「已补齐」+ 证据）

| 功能 | 矩阵 ID | 状态 | 证据路径 |
|------|---------|------|----------|
| 项目发起 / 列表 / 详情 | — | 部分 | Hub API `routes/projects.py`；前端待核对 |
| Agent 列表 + 活动预览 | — | 部分 | Hub API `routes/agents.py` |
| Workspace 频道 | — | 部分 | `routes/channels.py` |
| Token 用量展示 | R-O3 | 未验收 | `token-metering-change-log.md` — 后端接线完成，UI 待验 |
| 内核运行态 / 续跑 | R-K* | 后端完成 | `kernel-runs-change-log.md` |

## 下一步（P4 前）

1. product 轻量确认：`docs/executions/p3-2-product-light-confirm.md`（待创建）
2. 在矩阵上逐行标注「已补齐」与截图/路由证据
3. 禁止全文重写 `v1-v2-feature-matrix.md`（修正项 #5）
