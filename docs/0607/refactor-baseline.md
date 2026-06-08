# myteam 内核重构基线

**记录时间：** 2026-06-05  
**分支：** `upgrade/continued`

## 重构前指标

| 指标 | 值 |
|------|-----|
| `backend/common/process.py` 行数 | 979 |
| `backend/common/store.py` 行数 | 748 |
| 测试目录 | `backend/common/tests/` + `backend/hub/` |

## 不变量（重构期间禁止改动）

- Interaction 契约（6 种 kind）、Gate 规则、Store schema
- `run_kernel` CLI 参数与 exit code 语义
- Hub API 路径与响应形状

## Phase 1 目标

- 抽出 `process_types.py`, `plan_gate.py`, `agent_bootstrap.py`, `task_pipeline.py`
- `process.py` < 650 行
- `pytest backend` 全绿，行为等价

## Phase 2 目标

- 抽出 `decision_pipeline.py`（决策类 Interaction）、`plan_expansion.py`（静态展开）、`dag_dispatch.py`（纯函数调度）
- `process.py` < 300 行，仅保留编排入口
- 新增 `test_dag_dispatch.py`、`test_plan_expansion.py` 覆盖纯函数路径

## 设计模式选型（Phase 2）

| 模式 | 落点 | 收益 |
|------|------|------|
| Pipeline | `TaskPipeline` / `DecisionPipeline` | 按 Interaction kind 分治，单测可注入 fake port |
| Template Method | `DecisionPipeline.task_plan` / `evaluate` 门禁重试环 | 消除重复重试逻辑 |
| Functional Core | `dag_dispatch.deps_block` / `derive_project_status` | 零 mock 单测调度语义 |
| Strategy（已有） | `AgentPort.Transport`、`CLIAdapter` | 保持 adapter 隔离不变量 |

## 验收记录

| Phase | 日期 | pytest | process.py 行数 | 备注 |
|-------|------|--------|-----------------|------|
| 0 基线 | 2026-06-05 | — | 979 | 本文件创建 |
| 1 Extract | 2026-06-05 | 172 passed（common，7.6s） | 458 | 拆出 4 模块；集成测隔离 registry |
| 2 Pipeline | 2026-06-06 | 81 passed（内核子集，3.6s） | 260 | 拆出 decision/plan_expansion/dag_dispatch；+13 纯函数单测 |
