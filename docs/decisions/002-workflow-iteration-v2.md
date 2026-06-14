# ADR-002: Workflow Iteration v2 (LoopSpec v2)

## Status

Accepted (2026-06-14 方案包 `docs/0614`)

## Date

2026-06-14

## Context

myteam R-Loop v1（`loops[].body` + `until` OR 语义）已在 `loop_runtime.py` / `process._execute_loop` 落地，但存在：

- 状态机内嵌于 `process.py`（680+ 行），难单测、难扩展多 body 分支
- `until` 与 assess 语义混用；无 `assess` / `transition` 一等公民
- `_execute_loop` 硬编码 `work`/`review` body id
- Hub `project_events` 未暴露 loop 里程碑；无 `iterations[]` 维度

业务需 **通用 iteration 壳**：配置驱动 assess、marker 协议、body 分支，内核不做 LLM 调度。约束见 `FRAMEWORK_BOUNDARY.md`、`FRAMEWORK-FREEZE.md`（`process.py` 变更须 Owner 批准）。

**质量属性优先级**：1 可测试性 / Resume 确定性 2 配置可演进 3 v1 行为零回归 4 前后端 schema 一致

## Decisions（ADR-001 … ADR-006）

以下编号与 [`01-架构实施方案.md`](../0614/01-架构实施方案.md) §5 一致。

### ADR-001 — Marker 协议为主；JSON assess 仅窄口扩展

- **决策**：Assess 结论以交付物 **单行 marker**（`REVIEW: PASS/FAIL`、`ITERATION: PASS/CONTINUE/BRANCH` 等）为主路径；JSON 结构化结果仅作未来窄口扩展。
- **拒绝**：JSON 作为默认 assess 格式 — Agent 交付物已是 Markdown；JSON 增加 Gate 与模板分叉。
- **后果**：Gate 校验 marker 存在性；内核 `evaluate_transition` 只解析 marker，不读自然语言结论段。

### ADR-002 — 分支用 `bodies` + `next_body`；禁止 loop 内 full `task_plan`

- **决策**：多轮 task 组差异通过 YAML `loops[].bodies{key}` 与 `transition[].next_body` 声明；禁止在 loop 占位节点内 LLM 动态重规划 DAG。
- **拒绝**：loop 内 `task_plan` / 整图重规划 — 非确定性、难 Resume、违反 FRAMEWORK-FREEZE。
- **后果**：`instantiate_round_body_tasks(spec, round, body_key=…)`；`branch_selected` run_event（P2）。

### ADR-003 — Assess = body 内一步或 `assess.ref` 指向 body 任务

- **决策**：`loops[].assess.ref` 引用当前 body 内相对 id（如 `review` / `assess`）；assess 为 body DAG 一步，非独立子图。
- **拒绝**：独立 assess 子图 — 与现有 work→review 结构不一致，plan_gate 展开复杂。
- **后果**：`resolve_assess_task_id()` → `{loop_id}-r{n}-{ref}`；新 task_type `iteration-assess`（P0 注册）。

### ADR-004 — `loop_discussion` 在 assess 之后、transition 之前

- **决策**：群对齐 / PATCH 在 assess 交付物就绪后、`evaluate_transition` 之前；dispatch 使用 `assess_task_id`，不再 hardcode `work`/`review`。
- **拒绝**：讨论后再 assess — 讨论依赖 review/assess 交付物。
- **后果**：`loop_discussion_dispatch.dispatch_loop_round_done(assess_task_id=…)`（P1）；v1 兼容 `review_task_id` 别名。

### ADR-005 — 状态机下沉 `run_loop()`；`_execute_loop` 薄委托

- **决策**：主循环与 `LoopRoundState` 迁入 `loop_runtime.run_loop()`；`process._execute_loop` 仅构造 `RunLoopDeps` 并委托。
- **拒绝**：保持 Process 内聚 — Process 已过大；单测需隔离 loop 逻辑。
- **后果**：**须 FRAMEWORK-FREEZE Owner 书面批准**（F1–F8 清单）；不解冻 `task_pipeline` / `gate` / `submit_result` / `AgentPort`。

### ADR-006 — Resume 靠确定性 task id + `run_event`

- **决策**：从 `{project_id}:loop:{loop_id}` 的 `loop_round_done` / `loop_transition` 及 store 中 `*-r{N}-*` task id 重建 `LoopRoundState`。
- **拒绝**：专用 `loop_state` 表 — Store schema 封板；task id 模式 `{loop_id}-r{n}-{body_id}` 已稳定。
- **后果**：`reconstruct_loop_state()` 单测；无 migration。

## 开放问题（方案内已落地）

| 问题 | 决议 | 阶段 |
|------|------|------|
| `min_rounds` 与 assess 首轮 STOP 冲突 | 强制 continue 至 `min_rounds` | P1 |
| Branch 完成后占位节点 | auto-complete，meta `loop_state=branched` | P2 |

## Consequences

- **正面**：v1 YAML 100% 行为不变；v2 增量启用；状态机可单测；Hub 可观测 iteration 维度。
- **代价**：P0–P3 分 PR 交付；`process.py` 变更走 Freeze 流程；前后端须以 Hub `validate_workflow` 为 schema 真源。
- **重新评估触发**：需 loop 内 LLM 重规划 / 非 marker assess / Store schema 变更。

## References

- [`00-总方案-通用Workflow迭代V2.md`](../0614/00-总方案-通用Workflow迭代V2.md)
- [`01-架构实施方案.md`](../0614/01-架构实施方案.md)
- [`FRAMEWORK-FREEZE.md`](../FRAMEWORK-FREEZE.md)
