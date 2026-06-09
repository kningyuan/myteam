# Sprint 0 执行追踪 — 2026-06-08

**目标**：L1 可靠性底座第一批（S1~S4）  
**发版门禁**：pytest 全绿 + REG-01 通过（后续 REG-02 证明 K1≥80%）

## 任务状态

| ID | 任务 | 状态 | 验收 | 评审 |
|----|------|------|------|------|
| S1 | `AdapterTransport` 注入 AGENTS.md/rules | ✅ 完成 | `test_transport_injects_rules_file` | QA PASS |
| S2 | `skill_config.process_defaults` → 内核 | ✅ 完成 | `kernel_config.py` + `server.py` | QA PASS |
| S3 | 设置 Tab 协作引擎参数 UI | ✅ 完成 | PUT skill-config 含 process_defaults | QA PASS |
| S4 | 发起项目 split checkbox | ✅ 完成 | payload.split=true | QA PASS |
| S5 | 删 claude/opencode 600s 墙钟 | ✅ 完成 | adapter 无墙钟 | QA PASS |
| S6 | pytest 回归 | ✅ 56 passed | 2.83s | QA PASS |

## 评审记录

| 时间 | 评审方 | 结论 | 备注 |
|------|--------|------|------|
| 2026-06-08 | QA | S1~S5 PASS | 可进 REG-01；REG-02 待 P0-D |
| 2026-06-08 | 架构师 | 3/4 PASS | rules 已去除 hub 间接依赖 |
| 2026-06-08 | 产品 | 2周承诺线明确 | 不自承诺小红书/无人值守 |

## 未纳入本 Sprint（L1 后续）

- P0-D 孤儿交付物回收（REG-04）
- P0-C2 token 计量定位（REG-05）
- REG-02 dogfooding 重跑
