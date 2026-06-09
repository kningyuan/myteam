# R-K17 Gate retry session 可观测 — 实现说明

| 字段 | 内容 |
|------|------|
| 需求 ID | R-K17（对应 R-K-H） |
| 状态 | ✅ 已完成 |
| 日期 | 2026-06-09 |

## 交叉评审共识（三角色）

| 角色 | 裁决 |
|------|------|
| 架构师 | `gate_retry_session` 仅写在 **interaction** 级 run_event；不进入 project feed `_FEED_KINDS`；与 K2 指标正交 |
| QA | `gate_failed` payload 补 `session_id`；扩展现有 `test_gate_retry_reuses_session`；REG 用 `reg_k17_gate_retry.py` |
| 工程 | 最小改动：`AdapterTransport.__call__` 在 `attempt>1` 且 resolver 返回 session 时 `ctx.emit` |

## 背景

Gate 重试已能复用上一轮 CLI `session`（`resolve_gate_retry_session`），但 observability 层无法从 run_event 区分「新会话」与「续聊重试」，排障与 K2 分析不便。

## 验收

- [x] attempt>1 且复用 session 时写入 `gate_retry_session`（含 session_id、attempt、task_id、project_id）
- [x] 首轮 `gate_failed` payload 含 `session_id`（若当轮已有 session 事件）
- [x] `test_gate_retry_emits_gate_retry_session_event`
- [x] `test_gate_retry_reuses_session` 断言上述两类事件
- [x] `reg_k17_gate_retry.py` PASS

## 改动文件

- `backend/common/agent_transport.py` — emit `gate_retry_session`
- `backend/common/task_pipeline.py` — `gate_failed.session_id`
- `backend/common/tests/test_agent_transport.py`
- `backend/common/tests/test_process.py`
- `scripts/regression/reg_k17_gate_retry.py`

## 回归

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest \
  backend/common/tests/test_agent_transport.py::test_gate_retry_emits_gate_retry_session_event \
  backend/common/tests/test_process.py::test_gate_retry_reuses_session -q

MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend python3 scripts/regression/reg_k17_gate_retry.py
```
