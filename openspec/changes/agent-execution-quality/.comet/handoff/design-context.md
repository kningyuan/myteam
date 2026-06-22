# Comet Design Handoff

- Change: agent-execution-quality
- Phase: design
- Mode: compact
- Context hash: 8fb4220d1df1d46bc4d6db5bdd19245b32ededaf576655ac60790546fb502bf9

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/agent-execution-quality/proposal.md

- Source: openspec/changes/agent-execution-quality/proposal.md
- Lines: 1-32
- SHA256: d8ea7e04012ee78cdc532ee8db7d4ae6867f8689b1a0a23a89a4b939caba1bee

```md
## Why

myteam 的 L1/L2 协作内核已稳定，但单 Agent 执行任务的质量缺乏系统性的保障机制。每次 execute 交互可能因方向偏差导致多次 Gate retry，同类错误在不同项目中反复出现，团队配置依赖人工经验而非数据支撑。Agent 执行质量的波动，是团队协作质量的瓶颈。

通过在 Execution Harness 层增加 Plan-then-Execute 前置规划、失败模式分类引导、经验教训回授、以及 Agent 质量画像，从根本上提升单 Agent 任务交付质量，团队协作质量自然随之提升。

## What Changes

- **Plan-then-Execute（路径 A）**：execute 前插入 plan 交互，agent 先出 approach/steps/risks，通过轻量 Gate 后作为参考注入 execute prompt
- **重试策略升级（路径 D）**：Gate 失败时按 5 类模式分类（章节缺失/内容空洞/格式错误/超时中断/偏离计划），给出可操作的修正指引
- **经验教训回授（路径 B）**：task 有 retry 时自动从 ledger 提取 pitfalls/lesson 写入 KB，下次同类任务 PRE 阶段注入
- **Agent 质量画像（路径 C）**：每次 task 完成记录 quality 指标（attempt/score/gate/review），跨项目持久化，team_config 时注入供决策参考

## Capabilities

### New Capabilities

- `plan-prompt`: execute 前置 plan 交互契约与 Gate 校验
- `gate-retry-feedback`: Gate 失败模式的 5 类自动分类与可操作指引
- `lesson-feedback-loop`: 任务教训的 ledger→KB→PRE 注入全链路
- `agent-quality-profile`: 跨项目 agent 质量指标记录与摘要

### Modified Capabilities

- （无，本次不涉及 specs 层的需求变更）

## Impact

- **backend/execution_harness/**: 新增 post/failure_patterns.py、post/lesson.py、post/_yaml_util.py、post/quality.py、pre/lesson_inject.py
- **backend/common/**: contracts.py 新增 plan 契约、gate.py 新增 check_plan、task_pipeline.py 新增 run_plan 和 _record_quality、agent_transport.py 新增 plan prompt、decision_pipeline.py 新增质量注入
- **测试**: backend/common/tests/test_failure_patterns_lesson.py（29 测试用例）
- 零前端改动、零配置改动
```

## openspec/changes/agent-execution-quality/design.md

- Source: openspec/changes/agent-execution-quality/design.md
- Lines: 1-75
- SHA256: 09b93dd2b6e7f972f112551f52d9059fbf3d6e1e14cc55854d651fbf57b1e00c

```md
## Context

myteam 的 Agent 执行流程目前是 `execute → Gate → POST`，缺少执行前的规划环节，Gate 失败时反馈原始、缺乏可操作性，经验仅在 ledger 中沉淀但未形成跨项目复用，团队决策缺乏质量数据支撑。

本变更在 Execution Harness 层（Layer A）增加 4 个正交能力，不触及 L1/L2 内核（Process/DAG/AgentPort）。

## Goals / Non-Goals

**Goals:**
- execute 前有结构化规划 -> 减少方向性 retry
- Gate 失败时给出分类原因 + 可操作指引 -> retry 效率提升 ≥20%
- 教训跨项目复用 -> 同类错误不再重复犯
- agent 质量跨项目可查 -> team_config 做数据驱动决策

**Non-Goals:**
- A/B 实验引擎（路径 E，P2 暂缓）
- 内核状态机重构（framework freeze 不变）
- 前端 UI 改动
- 业务 skill 内容改动

## Decisions

1. **Plan 作为独立 Interaction kind（非 execute 子模式）**
   - 选择：新增 `kind=plan` 契约，独立 `PlanResult`、`PlanResponse`
   - 理由：契约体系已有 8 种 kind，plan 与 execute 正交，复用 AgentPort/watchdog 生命周期
   - 替代方案：execute prompt 开头要求写 plan → 均摊 token 但无法独立 Gate 校验

2. **Gate 失败模式按 5 类分类**
   - 选择：章节缺失/内容空洞/格式错误/超时中断/偏离计划
   - 理由：覆盖现存所有 Gate rule 类型，每类有独立指引文案
   - 限制：超时中断 (timeout_interrupt) 不来自 Gate，需端口状态显式设置

3. **教训使用 Store.memory（非单独的 KB 后端）**
   - 选择：`store.memory_write` + tag `["lesson", task_type, agent_id]`
   - 理由：与质量画像、经验条目统一后端，无需额外依赖
   - 替代方案：memstack.kb → 两套存储，增加复杂度

4. **质量画像注入 team_config（非独立分析面板）**
   - 选择：`_quality_team_hint()` → team_config input
   - 理由：改动最小，利用已有的决策类交互展示质量数据

## Architecture

```
execute 前:
  run_task() → run_plan() → Gate.check_plan() → save to task meta
                                                     ↓
  execute prompt 中:  context.plan → 【执行前计划】块

execute 失败:
  Gate.check_execute() → classify_failures() → enriched retry_feedback
  agent 收到: 【失败根因分类】+【类别指引】+【失败详情】

execute 成功:
  _finalize_success() → _record_quality() → KB (tags: quality/agent/task_type)
                       → (if attempt>1) write_lesson_entry() → KB (tags: lesson/agent/task_type)

下一次 execute 前:
  PRE inject_execute_prompt() → append_experience_hints()
                               → append_lesson_hints()  ← 新增
                               → (team_config) _quality_team_hint()  ← 新增
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Plan 增加一次交互 token 开销 | Plan 约 3-5K tokens，远小于一次 retry（50-200K），净收益为正 |
| Lesson 写入条件 attempt>1 过于保守 | 可配置，默认保守避免低价值数据 |
| Quality 数据依赖 agent 自评分 | 配合 review 结果交叉验证 |
| CJK 字符阈值偏差 | 使用 ≥2 字符作为 CJK 下限 |

## Open Questions

- 路径 E（实验引擎）何时引入？建议 2-3 个月后 D+B+A+C 效果验证后再做
```

## openspec/changes/agent-execution-quality/tasks.md

- Source: openspec/changes/agent-execution-quality/tasks.md
- Lines: 1-41
- SHA256: 703dc6e8e983983a113f9dd497e12835e8a3ba5198843bdd2bb211f6604e56ef

```md
## 1. 契约与门禁

- [x] 1.1 新增 `PlanResult`、`PlanResponse` 契约（contracts.py）
- [x] 1.2 新增 `check_plan()` 轻量门禁（gate.py）
- [x] 1.3 `Kind` 加 `"plan"` 辨识联合

## 2. 重试策略升级（路径 D）

- [x] 2.1 失败模式分类模块（post/failure_patterns.py）
- [x] 2.2 Gate 反馈 → 分类摘要 + 可操作指引（task_pipeline.py）
- [x] 2.3 Agent 侧结构化 retry 反馈显示（agent_transport.py）

## 3. 经验教训回授闭环（路径 B）

- [x] 3.1 Lesson 写入模块（post/lesson.py）
- [x] 3.2 PRE 教训注入模块（pre/lesson_inject.py）
- [x] 3.3 共享 YAML 解析器（post/_yaml_util.py）
- [x] 3.4 POST 集成 lesson 写入（facade.py）
- [x] 3.5 PRE 集成 lesson 注入（pre/inject.py）
- [x] 3.6 配置开关（config.py）

## 4. Plan-then-Execute（路径 A）

- [x] 4.1 Plan prompt 构建（agent_transport.py）
- [x] 4.2 `run_plan()` 预执行交互 + plan 存入 task meta（task_pipeline.py）
- [x] 4.3 Execute prompt 注入 plan 块（agent_transport.py）
- [x] 4.4 `plan_enabled` 配置开关（process_types.py）

## 5. Agent 质量画像（路径 C）

- [x] 5.1 质量记录模块（post/quality.py）
- [x] 5.2 Quality 写入 task 完成回调（task_pipeline._record_quality）
- [x] 5.3 Team_config 质量注入（decision_pipeline._quality_team_hint）

## 6. 测试与验证

- [x] 6.1 单元测试：29 项契约/Gate/Lesson/Quality 测试
- [x] 6.2 集成测试：39 项核心测试通过
- [x] 6.3 端到端实测：run_kernel.py 真实 Claude API 调用验证
  - Plan 确认：5 个真实任务通过 check_plan
  - Quality 确认：5 条质量记录写入 KB
  - Lesson 确认：任务一次通过无需 retry（预期行为）```

