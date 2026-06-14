# 0614 — 通用 Workflow 迭代 v2 方案包

> 日期：2026-06-14  
> 目标：通用 workflow 原语覆盖大部分业务场景；场景差异仅通过 YAML / 模板 / Skill 配置。

## 文档索引

| 文档 | 说明 | 状态 |
|------|------|------|
| [00-总方案-通用Workflow迭代V2.md](./00-总方案-通用Workflow迭代V2.md) | **主方案**（产品、架构、分期、验收） | ✅ 已定稿 |
| [01-架构实施方案.md](./01-架构实施方案.md) | 架构：ADR、状态机、`run_loop()`、Hub 契约 | ✅ 已定稿 |
| [02-研发实施方案.md](./02-研发实施方案.md) | 研发：PR1–PR4 任务表、代码草图、人日估算 | ✅ 已定稿 |
| [03-测试与回归方案.md](./03-测试与回归方案.md) | 测试：金字塔、REG 脚本、PR 门禁 | ✅ 已定稿 |
| [04-真实环境验证方案.md](./04-真实环境验证方案.md) | LIVE 试跑、Hub v2、证据与签字 | ✅ 已定稿 · **P1/P2 无 LIVE 预检 PASS**（2026-06-14） |

## 关联文档

- [DESIGN-WORKFLOW-LOOPS.md](../DESIGN-WORKFLOW-LOOPS.md) — R-Loop v1 设计（将扩展）
- [FRAMEWORK_BOUNDARY.md](../FRAMEWORK_BOUNDARY.md) — 内核 / 业务边界
- [FRAMEWORK-FREEZE.md](../FRAMEWORK-FREEZE.md) — Process 变更须批准
- [RECURRING_OPS.md](../RECURRING_OPS.md) — 跨周期 recurring（与 iteration 正交）

## 执行顺序

```text
P0  schema + 可观测 + 文档/模板     ← ✅ 已收口
P1  assess + transition 运行时      ← ✅ 已实现 · CHECK_ONLY 预检 PASS（2026-06-14）
P2  bodies 分支 + 试点 workflow     ← 🔄 YAML/REG 待交付 · LIVE 阻塞 claude CLI
P3  hook 窄口（可选）
```
