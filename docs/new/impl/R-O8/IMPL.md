# R-O8 结构化审计日志 — 实现说明

| 字段 | 内容 |
|------|------|
| 需求 ID | R-O8 |
| 状态 | ✅ 已完成 |
| 日期 | 2026-06-09 |

## 交叉评审共识

| 角色 | 裁决 |
|------|------|
| 架构师 | 沿用 `run_event` 作为审计载体，不新增重型审计表；审计能力属于 Observability/System Kernel |
| QA | request/response snapshot 必须含 hash、agent_id、outcome；篡改 payload 后校验失败 |
| 工程 | 在 `audit_log.py` 提供稳定 JSON hash 与校验函数；`AgentPort` 只增强既有 snapshot payload |

## 背景

原实现只在开启 `audit_log` 后保存 request/response snapshot，缺少稳定 hash 与可验证字段，无法满足「篡改日志行会导致 hash 不符」的验收。

## 验收

- [x] `request_snapshot` 含 `request_hash`、`agent_id`、`outcome`
- [x] `response_snapshot` 含 `response_hash`、`agent_id`、`outcome`、`outcome_kind`
- [x] `verify_audit_snapshot()` 能识别篡改后的 payload
- [x] `test_audit_log.py` 全量通过
- [x] `reg_o8_audit_log.py` PASS

## 改动文件

- `backend/common/audit_log.py`
- `backend/common/agent_port.py`
- `backend/common/tests/test_audit_log.py`
- `scripts/regression/reg_o8_audit_log.py`
- `scripts/regression/run_regression.sh`

## 回归

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/tests/test_audit_log.py -q
MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend venv/bin/python3 scripts/regression/reg_o8_audit_log.py
./scripts/regression/run_regression.sh --suite framework
```
