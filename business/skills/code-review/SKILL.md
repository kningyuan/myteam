---
name: "代码评审"
task_type: code-review
description: 代码评审 — 变更摘要、审查意见、优点、结论（带文件/行号引用）。
---
# code-review — 代码评审

**必须先读**（内核按 agent_id 注入）：
- `developer` → `business/skills/backend-engineering-methodology/SKILL.md`
- `frontend` → `business/skills/frontend-engineering-methodology/SKILL.md`
- `qa` → `business/skills/qa-methodology/SKILL.md`（质量与回归视角）

## Gate 章节（H2 须与 templates.yaml `code-review` 逐字一致）

| 章节 | 要求 |
|------|------|
| 变更摘要 | 改了什么、为何改 |
| 审查意见 | 分级：阻塞 / 建议 / nit；**须带文件路径或行号** |
| 优点 | 至少 1 条具体优点 |
| 结论 | 通过 / 需修订 / 阻塞合并；与意见一致 |

## 执行步骤

1. 读上游 diff 说明或实际变更文件（未读代码不得写「通过」）。
2. 对照 API 契约 / P0 清单：是否越 scope、是否破坏对称读写。
3. 审查意见表格或列表；阻塞项须可执行修复建议。
4. 结论与最高严重级别一致（有阻塞 → 不得「通过」）。

## qa 专责（质量与回归视角）

按 `qa-methodology` 补充，**不替代** Gate 四章节：

1. 对照上游 test-plan / P0 验收项：变更是否引入**未覆盖**的回归风险。
2. 审查意见须标注：受影响用例 ID、建议补测命令（如 `pytest … -q`）。
3. 无测试证据的「行为变更」→ 至少标为 **建议**；P0 路径无覆盖 → **阻塞**。
4. 结论与测试计划追溯一致；不得在无 rerun 证据时写「回归无影响」。

## 红线

- 禁止空泛「代码质量不错」
- 禁止无文件引用的审查意见
- 禁止代替 author 直接改代码（review 产出是报告）
