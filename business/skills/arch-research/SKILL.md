---
name: arch-research
task_type: arch-research
description: 架构向桌面调研 — delivery_profile light_v1
agents:
  - arch
  - developer
---

# arch-research — 架构调研（task_type Router）

**delivery_profile**：`light_v1`  
**与 `product-research` 区别**：架构/技术视角；产品向调研用 `product-research`。

## 必读

- `business/playbooks/ALL.md`
- `business/playbooks/scripts/scaffold_light.sh`

## 执行

```text
scaffold_light.sh → align.md → deliverable → verify.log → submit_result
```

## 章节

调研背景、信息来源、关键发现、结论（架构视角：模块、技术栈、风险）。
