---
name: decision-record
task_type: decision-record
description: 阶段决策记录 — 评审汇总、采纳决策、阻塞项与结论。
---

# decision-record — 决策记录

**main 必须先读**：`business/skills/coordination-methodology/SKILL.md`（阶段汇总纪律）  
**产品独立交付**（无 main）：`business/skills/product-operations/SKILL.md`  
**多角色 workflow**：通常由 `main` 执行；product 只读上游。

## 执行步骤

1. 读上游 strategy / acceptance / docs 交付物。
2. 骨架：`business/skills/product-operations/templates/decision_memo.md`
3. Gate 须含：**结论**、**开放 🔴：0**（或列出开放数）。

## 红线

- 禁止无依据的「通过」结论。
- 阻塞项须可追踪到具体交付物章节。
