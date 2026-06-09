# R-K-E 交互级 budget 硬停 — 实现说明（示范）

| 字段 | 内容 |
|------|------|
| 需求 ID | R-K-E（对应 R-K5） |
| 状态 | ✅ 已完成 |
| 日期 | 2026-06-09 |

## 背景

`AgentPort` 在交互循环中已有 `budget_checker`，但 execute 路径将 `budget_exceeded` 当作普通 **task failed**，项目未进入 **paused**。

## 验收

- [x] 交互进行中超预算 → `budget_exceeded` run_event
- [x] `task_pipeline` 抛 `BudgetExceededError`
- [x] `Process.run` / `resume` 捕获 → `project.status=paused`
- [x] `test_execute_budget_exceeded_pauses_mid_interaction` PASS

## 改动文件

- `backend/common/task_pipeline.py`
- `backend/common/process.py`（`resume` try/except）

## 回归

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest \
  backend/common/tests/test_observability.py::test_execute_budget_exceeded_pauses_mid_interaction \
  backend/common/tests/test_agent_port.py::test_agent_port_budget_hard_stop -q
```
