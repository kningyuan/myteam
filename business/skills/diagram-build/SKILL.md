---
name: 架构图构建
description: diagram-build 任务路由 — brief → draw.io → PNG；脚本与规范见 business/means/diagram-build。
task_type: diagram-build
---

# 架构图构建（diagram-build）

本 skill 为 **means 驱动** 任务：先读本文件，再读 means 执行说明与脚本。

## 必读

1. `business/means/diagram-build/EXECUTION.md` — 端到端流程
2. `business/skills/catalog.yaml` 中 `diagram-build` 条目的 `means` / `probe` / `verify`

## 交付物

- `diagram.drawio`
- `diagram.png`

## 红线

- 不得跳过 `probe.sh` / `verify_diagram.py` 即宣称完成
- 图须与 brief 中的实体、关系一致，禁止占位框糊弄 Gate
