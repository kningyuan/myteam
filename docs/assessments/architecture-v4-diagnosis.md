# Architecture v4 边界诊断

> **Workflow**：`myteam-architecture-v4` · 任务 `arch-audit`  
> **关系**：扩展 `myteam-platform-v3`，不替换 v3 诊断交付物  
> **扫描时间**：2026-06-14 post-refactor（`wc` / `rg` 实证，非估算）

---

## 1. 体量快照

| 对象 | 行数 | 路径 | 备注 |
|------|------|------|------|
| Hub monolith | **865** | `backend/hub/api/server.py` | v4 Wave 3–4 后自 1540 → **865**（−675） |
| Store 实现 | **1082** | `backend/common/store.py` | 薄门面委托 `StoreBackend` |
| StoreBackend 端口 | **49** | `backend/common/store_backend.py` | `Protocol` + `AbstractStoreBackend` + `SqliteStoreBackend` |
| Frontend API barrel | **2** | `frontend-v2/src/lib/api.ts` | 纯 re-export → `./api/index` |
| Frontend API 域模块 | **1224** | `frontend-v2/src/lib/api/*.ts` | 7 域 + client + index（**单轨**，无 legacy 双轨） |
| Hub 路由总计 | **~93** | `backend/hub/api/**/*.py` | app + router 装饰器合计 |
| Hub 路由（server.py） | **37** | `@app.*` 装饰器 | 仍含 agents CRUD、task-types、delivery-templates、obs/agents |
| Hub 路由（routes/ + obs + skills） | **~56** | `@router.*` 等 | 9 域模块 + observability + skills |
| routes/ 文件数 | **10** | `hub/api/routes/*.py` | 9 域路由 + `__init__.py` 聚合 |

### Wave 进度（对照 api-split-plan.md）

| Wave | 域 | 状态 |
|------|-----|------|
| 1 | channels | ✅ `routes/channels.py`（4 端点） |
| 2 | workspace/events, jobs, projects list/run | ✅ `routes/workspace_events.py`、`jobs.py`、`projects.py` |
| 2 部分 | obs/* | ✅ `observability_api.py`（12 端点） |
| 3 | agents/backends/config | ✅ `routes/config.py`（14 端点）；agents list ✅；agents CRUD 部分仍驻留 server |
| 4 | chat, groups | ✅ `routes/chat.py`（7）、`routes/groups.py`（20） |
| 5 | workflows, task-types, delivery-templates, skills | ✅ `routes/workflows.py`（6）、`skills_api.py`（4）；task-types / delivery-templates 仍驻留 server |

**目标差距**：`server.py` 需从 865 → **< 400**（仅装配层 + SPA fallback）。

---

## 2. StoreBackend 端口

| 项 | 现状 |
|----|------|
| `StoreBackend` Protocol / ABC | **存在** — `backend/common/store_backend.py` |
| 默认实现 | `SqliteStoreBackend` |
| `Store` 类 | 薄门面，构造时注入 `StoreBackend`（默认 SQLite） |
| PG 后端代码 | **0**（设计见 `pg-migration-plan.md`） |
| 直写 bypass（生产） | **0**（group_manager 已收拢，v3 审计确认） |

---

## 3. Adapter 层

| 类别 | 数量 | 路径 |
|------|------|------|
| 生产 CLI adapter | **2** | `adapters/claude/adapter.py`, `adapters/opencode/adapter.py` |
| 计划 stub adapter | **2** | `adapters/stub_cli.py` — **codex**、**cursor** 注册为 `PlannedCLIAdapter` |
| adapter 基础设施 | **11** | `backend/adapter/*` + `backend/adapters/*` |

Adapter 与 Hub API **无直接耦合**（经 AgentPort / subprocess_cli）；边界清晰。

---

## 4. 耦合热点（import 扫描）

### 4.1 `server.py` 跨层 import

| 来源层 | 热点模块 |
|--------|----------|
| `base.*` | `agent_chat`, `agent_factory`, `group_manager`（遗留 handler） |
| `hub.services.*` | `project_launch`, `kernel_run` |
| `store.*` | `system_config`, `skill_config` |
| `hub.api.*` | `deps`, `errors`, `routes.api_router`, `observability_api`, `skills_api` |

**剩余风险**：agents CRUD、task-types、delivery-templates handler 仍内联于 server → Wave 5 收尾可再 −400 行。

### 4.2 已提取 routes 的依赖（健康）

```
routes/channels.py   → deps.we_store, errors.APIError
routes/projects.py   → deps, errors, hub.services.project_launch
routes/agents.py     → deps.we_store, errors
routes/config.py     → store.system_config, skill_config
routes/chat.py       → base.agent_chat, hub.services.sse_bridge
routes/groups.py     → base.group_manager
```

无 `routes → server` 反向 import。

### 4.3 前端 → 后端路径耦合

| 检查项 | 结果 |
|--------|------|
| frontend import backend Python 模块 | **0** |
| pages/components 内 `fetch(` | **0** |
| pages/components 内 `/api/` REST 字符串 | **0**（`@/lib/api/*` import 路径不计） |
| `lib/api` 外 `fetch(` | **0**（SSE 封装在 `client.ts` / 域模块） |
| `lib/api/*.ts` `/api/` 引用 | **77** | 全部 REST 路径 SSOT |
| pages 仍 import `@/lib/api` barrel | **~15** 处 | 可逐步切至域模块，路径封装合规 |

**结论**：前端 **运行时边界合规**；**源码结构合规**（api.ts 2 行 barrel，域模块单轨）。

---

## 5. Frontend API 路径分布

| 模块 | `/api/` 引用数 |
|------|----------------|
| `api/workflows.ts` | 20 |
| `api/projects.ts` | 18 |
| `api/groups.ts` | 15 |
| `api/agents.ts` | 10 |
| `api/config.ts` | 7 |
| `api/chat.ts` | 7 |
| `api.ts`（legacy） | **0**（已删除重复实现） |

---

## 6. 契约测试现状

| 测试 | 路径 | 覆盖 |
|------|------|------|
| 响应形状 | `backend/common/tests/test_api_contract.py` | overview、groups、summary、错误信封 |
| FE↔Hub 路由 parity | **`backend/common/tests/test_fe_hub_route_contract.py`** | 静态解析 `lib/api/*.ts` + FastAPI introspection；priority: projects/chat/groups/config |
| SSOT 文档 | `docs/HUB_API_CONTRACT.md` | 冻结 REST + SSE 名称；非机器可读 |

**2026-06-14 验**：parity 测试 **3/3 passed**；`pytest backend -q` **602 passed**。

---

## 7. 边界违规扫描

| 规则 | 违规数 |
|------|--------|
| frontend import backend 源码 | **0** |
| backend import frontend 组件/TS | **0** |
| UI 层直写 REST 路径 | **0** |
| Hub 路由无 FE parity 登记 | **0**（parity 测试覆盖 lib/api SSOT） |

---

## 8. v4 优先级建议

1. **P0 — server.py 收尾 < 400**：提取 agents CRUD、task-types、delivery-templates 至 routes/。
2. **P1 — barrel 收敛**：pages 从 `@/lib/api` 切至 `@/lib/api/<domain>`（可选，非阻塞）。
3. **P2 — PG StoreBackend**：可选第二实现，不阻塞 API 拆分。
4. **DONE — integration-test**：`test_fe_hub_route_contract.py` 已落地。

---

## 9. 证据命令（可复现）

```bash
wc -l backend/hub/api/server.py frontend-v2/src/lib/api.ts backend/common/store_backend.py
ls backend/hub/api/routes/*.py | wc -l
rg -c '@app\.(get|post|put|patch|delete)' backend/hub/api/server.py
rg -c '@router\.(get|post|put|patch|delete)' backend/hub/api/routes/ backend/hub/api/observability_api.py backend/hub/api/skills_api.py
rg '/api/' frontend-v2/src/lib/api/*.ts -c
rg 'fetch\(' frontend-v2/src/pages frontend-v2/src/components --glob '*.{ts,tsx}'
PYTHONPATH=backend pytest backend/common/tests/test_fe_hub_route_contract.py -q
PYTHONPATH=backend pytest backend -q
```
