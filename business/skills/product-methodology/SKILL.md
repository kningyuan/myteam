---
name: 产品方法论
description: 产品交付方法论：问题空间、用户场景、范围边界、可验证验收与优先级排序。
---
# 产品方法论（myteam 适配版）

> **来源合成**（已裁剪）：
> - Jobs-to-be-Done / 用户故事映射
> - PRD 最佳实践（In/Out Scope、可测试验收）
> - RICE / MoSCoW 优先级框架
> - 验收驱动开发（Acceptance Criteria 先行）

**myteam 红线**：产品交付 **可验证结论**，不把技术实现细节写成已定方案（留给 arch / system-design）。

---

## 何时启用

- `task_type` 为 requirements、strategy、product-planning、product-research、acceptance-report、section-authoring、section-review（产品视角）
- 用户问「需求怎么写」「验收标准」「范围怎么定」

---

## 执行流程（必须按序）

### Step 1 — 问题空间（Problem Space）

| 维度 | 内容 |
|------|------|
| 用户/客户 | 谁在用、在什么情境下 |
| 痛点 | 现状为何不够好（证据引用上游 research） |
| 成功指标 | 可观察的结果（非功能清单） |
| 非目标 | 本轮明确不做的事 |

**禁止**在未写非目标前堆功能列表。

### Step 2 — 用户与场景

- 至少 **2 个** 具体场景（When / I want / So that）
- 用户故事表：`角色 | 场景 | 价值 | 优先级(MoSCoW 或 P0/P1/P2)`
- 每个 P0 故事须对应下游可执行的 **R1/R2…** 验收标准

### Step 3 — 范围边界（Scope Contract）

交付物 **必须** 含：

```markdown
## In Scope
- …

## Out of Scope
- …（至少 3 条，防止 scope creep）
```

Out of Scope 是 Gate 硬要求，不可省略或合并进正文。

### Step 4 — 可验证验收标准

每条验收标准须满足 **SMART 测试性**：

| ID | 标准 | 验证方式 |
|----|------|----------|
| R1 | 给定…当…则… | 手动步骤 / 脚本 / 演示 |
| R2 | … | … |

**禁止**：「体验良好」「性能足够」等不可测试表述。

### Step 5 — 方案方向与优先级（strategy / planning）

- 可选方案 **≥2**，用表格对比维度（成本、风险、时间、依赖）
- 推荐方案 **1 句结论** + 不选其他的首要理由
- 策略类须含 **「不确定性」**：数据缺口、待验证假设、局限

### Step 6 — 验收报告专用（acceptance-report）

- 逐项对照上游 R1/Rn：**PASS / FAIL / 遗留 / 降级**
- 无 qa 日志或脚本 exit 0 证据 → 禁止写「全部通过」
- 发布建议须与遗留项一致（有 P0 遗留 → 不得建议全量发布）

---

## 与 task skill 的关系

| task_type | 本方法论侧重 | 任务 skill 侧重 |
|-----------|--------------|-----------------|
| requirements | Step 1–4 | PRD 骨架、playbook |
| strategy | Step 1–5 + 不确定性 | strategy_memo 模板 |
| product-research | Step 1 + 证据引用 | light_v1 调研章节 |
| product-planning | Step 2–5 + 架构图 | 可信数据空间等专项 |
| section-authoring | Step 2–4 + 范围对齐 | 方案编制五章 Gate |
| section-review | Step 4 验收视角（产品向） | 内容质量审计 |
| acceptance-report | Step 6 | 贯通验收脚本 |

先走本方法论框架，再执行 `business/skills/<task_type>/SKILL.md` 的步骤与模板。

---

## 反模式（禁止）

- 把 UI 控件级设计写进 PRD（留给 frontend / arch）
- 无 Out of Scope 的「大而全」需求
- 验收标准无法被 qa 或脚本复现
- 策略文档无不确定性章节

---

## Pitfalls（常见踩坑）

- **冷启动瞎编**：未 Read 本 SKILL + 上游 research 就写结论 → 必须标注「待验证假设」
- **Scope creep**：In Scope 不断追加、Out of Scope 空白 → Gate 会拒
- **不可测试验收**：「体验好」「性能够」→ 改成 Given/When/Then 或可脚本化检查
- **越界写实现**：PRD 里定死 API/表结构 → 留给 arch / system-design
- **调研无过程**：全景调研须列出扫描路径、测试命令、文档/代码对照；禁止只读 README 就下结论

---

## Verification（交付前自检）

- [ ] 已 Read 本 SKILL.md 全文并按 Step 1–6 执行
- [ ] In Scope / Out of Scope 均非空（Out ≥ 3 条）
- [ ] 每条 P0 用户故事有 R1/Rn 可测试验收
- [ ] 策略/调研类含「不确定性」或「文档 drift」清单
- [ ] 引用的文件路径已核实存在（不存在须标明）
- [ ] `submit_result.metadata.chosen_skills` 含本方法论 id（若适用）
