---
name: requirements
task_type: requirements
description: PRD 级需求 — 范围、用户故事、可验证验收标准。
---

# requirements — 需求 / PRD

**必须先读**：`business/skills/product-methodology/SKILL.md`（范围、验收、优先级框架）  
**再读**：`business/skills/product-operations/SKILL.md`  
协作模式：`playbooks/team_handoff.md` · 独立模式：`playbooks/solo_delivery.md`

## 执行步骤

1. 读上游调研（若有）与【项目目标】/【本任务】。
2. 以 `business/skills/product-operations/templates/prd_outline.md` 为骨架编辑 deliverable。
3. Preflight：`checklists/prd_preflight.md`
4. **必须**含：
   - In Scope / **Out of Scope**
   - 用户故事表 + **R1/R2…** 验收标准（可测试）
   - 方案方向（可选方案对比）
5. 版本号写在标题或文首（v1 / v2）。

## 红线

- 禁止无验收标准的「需求」。
- 禁止把技术实现细节写成已定方案（留给 arch/system-design）。
- 禁止跳过 Out of Scope。
