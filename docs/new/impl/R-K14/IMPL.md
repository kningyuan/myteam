# R-K14 任务级 backend 路由 — 实现说明

| 字段 | 内容 |
|------|------|
| 需求 ID | R-K14 |
| 状态 | ✅ 已完成 |
| 日期 | 2026-06-09 |

## 交叉评审共识

| 角色 | 裁决 |
|------|------|
| 架构师 | 运行时读 `business/config/agents_config.json`（Hub `set_agent_backend_config` 写入）；`agents_registry.json` 仅名册，不含 backend |
| QA | 单 agent + 双 agent 并存不同 backend；`reg_k14_per_agent_backend.py` CHECK_ONLY |
| 工程 | `AdapterTransport._backend_for` + per-backend adapter 缓存；Process 无需改 |

## 验收

- [x] `test_transport_uses_per_agent_backend`
- [x] `test_transport_two_agents_different_backends`
- [x] `reg_k14_per_agent_backend.py` PASS

## 改动文件

- `backend/common/agent_transport.py`（既有 `_backend_for` / `_adapter_obj`）
- `backend/common/tests/test_agent_transport.py`
- `scripts/regression/reg_k14_per_agent_backend.py`

## 回归

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest \
  backend/common/tests/test_agent_transport.py::test_transport_uses_per_agent_backend \
  backend/common/tests/test_agent_transport.py::test_transport_two_agents_different_backends -q

MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend python3 scripts/regression/reg_k14_per_agent_backend.py
```
