---
name: 后端工程方法论
description: 后端工程方法论：契约优先、分层改动、Store/Port 边界、测试与最小回归。
---
# 后端工程方法论（myteam 适配版）

> **来源合成**（已裁剪）：
> - API 设计原则（资源导向、错误模型、幂等）
> - 分层 / 六边形在 myteam 的落地（Hub routes → services → Store）
> - 测试金字塔：单元 > 集成 > E2E

**myteam 红线**：读 `docs/FRAMEWORK-FREEZE.md`；禁止改 Process/AgentPort/Gate 语义；Store 为持久化真相；Hub 不 bypass Store。

---

## 何时启用

- `agent_id=developer` 且 code-writing / code-deliverable / code-review / system-design（实现向）
- Hub API、store、kernel_config、common 模块改动

---

## 执行流程（必须按序）

### Step 1 — 契约与范围

1. 读上游 **API 契约表** 与 P0/P1 清单
2. 每条实现对应清单 id；Out of Scope 不动
3. 新增端点须 workflow 明确要求 + arch 已列契约

### Step 2 — 分层落点

| 变更类型 | 首选位置 | 避免 |
|----------|----------|------|
| HTTP 路由 | `hub/api/routes/*.py` | server.py 继续膨胀 |
| 业务逻辑 | `hub/services/` 或 `common/` | 路由内大段逻辑 |
| 持久化 | `Store` / `store_sqlite` | 路由内裸 SQL |
| 外部 CLI | `adapter/` + Port | Hub 直接 subprocess |

大文件拆分遵循 **模块化单体**：按域拆 route 模块，不改部署单元。

### Step 3 — 实现原则

- **最小 diff**：只改完成任务所需的行
- **对称读写**：GET 与 PUT/PATCH 字段、默认值一致
- **错误可见**：API 返回可诊断的错误码/消息，勿吞异常
- **类型与测试**：新逻辑配 pytest；改 contract 配 route 测试

### Step 4 — 测试（保存前必跑）

```bash
cd myteam
PYTHONPATH=backend venv/bin/python3 -m pytest backend -q
bash business/skills/myteam-config-linkage/scripts/run_linkage_tests.sh
```

配置贯通类任务两者 **都须** exit 0。

### Step 5 — Store 与 Port 纪律

- 生产路径 **禁止** `_conn.execute` 绕过 Store API（测试夹具除外）
- 新存储抽象：先 `StoreBackend` Protocol，再 SQLite/PG 实现
- Adapter 变更不影响 `AgentPort` 调度契约

### Step 6 — 交付说明

与 frontend 相同表格：变更文件、P0/P1 对应、验证命令、回归结果。

Code-review 时检查：SQL 安全、LLM 信任边界、条件副作用（见 gstack-review 类检查项）。

---

## 与 system-architecture-methodology 的关系

| 阶段 | 方法论 |
|------|--------|
| 设计 system-design | system-architecture-methodology |
| 实现 code-writing | 本 skill + code-writing task skill |

设计结论落地时 **不得** 违背 ADR / trade-off 中已记录的约束。

---

## 反模式（禁止）

- 在 `server.py` 新增百行路由而不拆模块
- 为通过测试删断言或改期望
- 建议「重写内核」替代增量修复
- 未跑 pytest 就 submit
