---
name: strategy
task_type: strategy
description: 策略分析 — 背景、分析、方案、建议；须含不确定性。
---

# strategy — 策略分析

**先读**：`business/skills/product-operations/SKILL.md`

## 执行步骤

1. 读上游 requirements / research，**引用具体结论**，勿空泛复述。
2. 骨架：`business/skills/product-operations/templates/strategy_memo.md`
3. Gate 要求正文含 **「不确定性」** — 写局限、待验证点、数据缺口。
4. 四段式 H2：`背景` `分析` `方案` `建议`（与 templates.yaml 一致）。
5. 对比维度优先用 **表格**。

## 给 deck-build 下游

在「建议」末尾加 **「演示要点（供 PPT）」** 小列表（3–5 条），便于 t-deck 填 brief。

## 红线

- 禁止无「不确定性」章节或正文。
- 禁止忽略上游 requirements 的 R 验收标准。
- 禁止代替 arch 写详细技术 ADR。
