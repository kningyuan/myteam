# 协作模式 — product 在多 agent workflow 中的位置

## 方案编制

| 步 | agent | product 做什么 |
|----|-------|----------------|
| t-research | research | 只读上游，不代写调研 |
| t-req | **product** | PRD 范围与验收标准 |
| t-strategy | **product** | 策略四段式 |
| t-tech | arch | product 不主责；可读 t-strategy 评审可行性 |
| t-docs | docs | product 评审定稿是否偏离合结论 |
| t-accept | **product** | 对照 t-req 成功标准验收 |
| t-decision | main | product 只读，不抢 decision-record |

## 系统研发

- product：`requirements` 定义 R 验收；`acceptance-report` 终验
- 不把 code-writing 分给 product

## 交接格式

给下游 arch/developer 时，requirements 须含：

- **In Scope / Out of Scope** 明确列表
- **用户故事** 表格 + **验收标准 R1…Rn**（可测试）
- **开放问题** 单独列出，勿埋在正文

给 docs/content 时，strategy 的「方案」「建议」须可直接引用，避免指代不明。
