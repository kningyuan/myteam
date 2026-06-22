---
comet_change: agent-execution-quality
role: technical-design
canonical_spec: openspec
---

# Agent 执行质量提升 — 设计文档

## 架构概览

4 条正交路径在 Execution Harness 层（Layer A）工作，不触及 L1/L2 内核：

```
execute 前:
  run_task() → run_plan() → Gate.check_plan() → save to task meta
                                                     ↓
  execute prompt 中:  context.plan → 【执行前计划】块

execute 失败:
  Gate.check_execute() → classify_failures() → enriched retry_feedback
  agent 收到: 【失败根因分类】+【类别指引】+【失败详情】

execute 成功:
  _finalize_success() → _record_quality() → KB (quality/agent/task_type)
                       → (if attempt>1) write_lesson_entry() → KB (lesson/agent/task_type)

下一次 execute 前:
  PRE inject → append_experience_hints()
              → append_lesson_hints()  ← 新增
  team_config → _quality_team_hint()  ← 新增
```

## 路径设计

### 路径 A：Plan-then-Execute

- 新增 `kind=plan` 到 `InteractionRequest/Response` 辨识联合
- `PlanResult`: `approach(≥10字)` + `steps(≥1)` + `risks(可选)` + `confidence(可选)`
- `check_plan()`: 轻量门禁 — 仅检查结构完整性，不判质量
- `TaskPipeline.run_plan()`: plan 单次交互 → 存 task meta → 失败不阻塞 execute
- execute prompt 中 context.plan → 【执行前计划】块

### 路径 D：重试策略升级

- 5 类失败模式: section_missing / content_stub / format_error / timeout_interrupt / plan_drift
- Gate 反馈: 分类摘要 + 每类可操作指引 + 失败详情
- `_yaml_util.py` 共享 YAML 解析（消除 distill.py 与 lesson.py 重复）

### 路径 B：经验教训回授

- `post/lesson.py`: 从 ledger 提取 pitfalls/lesson，写入 KB 带 `["lesson", task_type, agent_id]`
- 触发条件: task 完成时 `attempt > 1`（有 retry 才有教训）
- `pre/lesson_inject.py`: 三级检索（项目 → 全局 → 跨 agent）→ 注入 prompt

### 路径 C：Agent 质量画像

- `post/quality.py`: 记录 agent/task_type/attempt/score/gate/review 到 KB
- `decision_pipeline._quality_team_hint()`: team_config 时注入质量摘要

## 数据流

```
Plan:   agent → plan prompt → PlanResult → Gate → task meta → execute prompt
Lesson: ledger → parse → store.memory → KB → PRE inject → prompt
Quality: task done → record_quality → KB → team_config → main agent
Failure: Gate result → classify_failures → retry_feedback → agent
```

## 验证结果

- 29 项单元测试通过
- 39 项集成测试通过  
- 2 轮端到端实测: 15 个真实任务，15 个 plan 写入，15 条 quality 记录
- Lesson 未触发 = 所有任务一次通过 Gate（预期行为）