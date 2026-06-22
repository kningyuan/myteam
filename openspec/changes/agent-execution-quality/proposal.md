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
