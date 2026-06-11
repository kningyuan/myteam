---
name: product-research
task_type: product-research
description: 产品向桌面调研 — delivery_profile light_v1
workflows:
  - 产品独立交付
agents:
  - product
---

# product-research — 产品调研（task_type Router）

**delivery_profile**：`light_v1`（align + verify，无 means/catalog）  
**与 `research` 区别**：产品视角章节与验收；架构/技术向调研应使用独立 task_type（如未来的 arch-research）。

## 必读

| 文档 | 路径 |
|------|------|
| ALL 过程 | `business/playbooks/ALL.md` |
| 脚手架 | `business/playbooks/scripts/scaffold_light.sh` |
| 共享包 | `business/skills/product-operations/SKILL.md` |

## 执行

```text
scaffold_light.sh → align.md → deliverable → verify.log → submit_result
```

## 交付章节

调研背景、信息来源、关键发现、结论（见 templates.yaml）。
