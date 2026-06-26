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
