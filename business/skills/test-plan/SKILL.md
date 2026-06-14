---
name: test-plan
task_type: test-plan
description: 测试计划 — 范围、策略、用例与追溯矩阵。
agents:
  - qa
---

# test-plan — 测试计划

**必须先读**：`business/skills/qa-methodology/SKILL.md`

## Gate 章节（H2 须与 templates.yaml `test-plan` 逐字一致）

| 章节 | 要求 |
|------|------|
| 测试范围 | 模块列表、风险排序、策略、不在范围 |
| 测试用例 | 用例总表（ID、场景、步骤、期望、优先级、追溯 R） |
| 正常路径 | 主流程用例分组 |
| 边界条件 | 边界/等价类用例分组 |
| 异常路径 | 错误处理与失败路径用例分组 |

## 执行步骤

1. 读上游 requirements / system-design 的 **R1/Rn** 与 P0/P1 清单。
2. 按 qa-methodology Step 1–3 写 **测试范围、风险、策略**。
3. 用例表须含：ID、场景、步骤、期望、优先级、追溯(R)；可按 **正常路径 / 边界条件 / 异常路径** 分组。
4. 交付物 H2 标题须与上表 Gate 章节逐字一致（`## 测试范围` … `## 异常路径`）。
5. **风险与策略**（qa-methodology Step 1–2）写入 `## 测试范围` 或其下小节，勿另起 Gate 未登记的 H2。
6. 每条 P0 验收项至少一条 P0 用例覆盖。

## 红线

- 禁止无追溯列的用例表。
- 禁止「全面测试」而无具体模块列表。
- 禁止无命令/脚本引用的「自动化策略」。
