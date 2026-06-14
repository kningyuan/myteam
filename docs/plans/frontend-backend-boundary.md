# 前后端边界计划（REST 契约 SSOT）

> **Workflow**：`myteam-architecture-v4`  
> **扩展**：`myteam-platform-v3` P2.1 api-split-plan、P2.4 pg-migration-plan  
> **诊断基线**：`docs/assessments/architecture-v4-diagnosis.md`

---

## 1. 原则

前后端是**独立部署单元**，仅通过 **HTTP REST + SSE** 通信。共享的是**契约文档与测试**，不是源码。

| 允许 | 禁止 |
|------|------|
| frontend `hubFetch('/api/...')` 经 `lib/api/*` | frontend `import` backend Python/路径 |
| backend 挂载 `frontend-v2/dist` 静态资源 | backend `import` frontend TS/TSX 源码 |
| 契约文档 + pytest 形状/路由 parity 测试 | pages/components 内写 `/api/` 或 `fetch(` |
| _additive_ 字段扩展（HUB_API_CONTRACT 约定） | 无登记地删除/重命名响应字段或 SSE 事件名 |

---

## 2. REST 契约 SSOT

### 2.1 权威来源（优先级）

1. **`docs/HUB_API_CONTRACT.md`** — 冻结面（REST 路径、SSE 事件名、消息形状）；人工维护，additive-only。
2. **`backend/common/tests/test_api_contract.py`** — 响应**形状**回归（overview keys、groups 字段、错误信封）。
3. **v4 新增：`test_fe_hub_route_parity.py`**（`integration-test` 任务）— FE 声明路径 ↔ Hub 注册路由 **method + path** 对齐。
4. **OpenAPI** — **可选 future**：由 FastAPI `app.openapi()` 生成，不作为 v4 阻塞项；生成后作为 HUB_API_CONTRACT 的补充视图，不替代 SSOT 文档中的 SSE 与行为说明。

### 2.2 变更流程

```
需求 → 更新 HUB_API_CONTRACT.md → 实现 Hub 路由 → 实现 lib/api Port → 更新 contract tests → arch-gate
```

增删路径或字段时，**测试必须先红后绿**；禁止「先改代码后补文档」。

---

## 3. Backend 边界

### 3.1 Hub API 分层

```
frontend-v2
    │ HTTP/SSE
    ▼
hub/api/server.py          ← 仅：FastAPI app、lifespan、middleware、静态文件、include_router
hub/api/routes/*.py        ← 域路由（Wave 3–5）
hub/api/deps.py            ← Store 单例等共享依赖
hub/api/errors.py          ← APIError
hub/services/*.py          ← 业务编排（project_launch, kernel_run）
backend/common/store.py    ← Store 门面 → StoreBackend 端口
backend/base/*             ← 领域逻辑（group_manager, agent_chat）
```

**规则**：`routes/*.py` 不得 `import server`；handler 通过 `deps` 取 Store，通过 `services` 调编排。

### 3.2 StoreBackend 端口（backend-ports）

```python
# 目标结构（见 pg-migration-plan.md §3）
# backend/common/store_backend.py — Protocol
# backend/common/sqlite_store_backend.py — 默认实现
# backend/common/store.py — 薄门面，方法签名不变
```

- Hub 与 kernel **只依赖 `Store` 公开方法**，不依赖 sqlite3 细节。
- 可选 PG 实现作为第二 `StoreBackend`，由 `MYTEAM_DB_BACKEND` 选择。

### 3.3 API Wave 3–5（backend-ports）

| Wave | 提取目标 | 预期 server.py 减量 |
|------|----------|---------------------|
| 3 | `routes/agents.py`（CRUD/config/events）、`routes/backends.py`、`routes/config.py` | ~−200 行 |
| 4 | `routes/chat.py`、`routes/groups.py` | ~−400 行 |
| 5 | `routes/workflows.py`、`routes/task_types.py`、`routes/delivery_templates.py`；projects 剩余端点并入 `routes/projects.py` | ~−500 行 |

**验收**：`server.py` < 400 行；`rg '@app\.(get|post)' server.py` 仅 health/static/SPA。

---

## 4. Frontend API 层 {#frontend-api-layer}

### 4.1 目标结构

```
frontend-v2/src/lib/api/
  client.ts       ← 传输 Port：hubFetch, SSE helpers（无域路径）
  projects.ts     ← ProjectsPort
  agents.ts       ← AgentsPort
  chat.ts         ← ChatPort
  groups.ts       ← GroupsPort
  workflows.ts    ← WorkflowsPort
  config.ts       ← ConfigPort
  index.ts        ← barrel re-export（对外稳定 import 路径）
```

- **`api.ts`（legacy）**：迁移完成后 **删除或 < 50 行** pure re-export。
- **pages/components**：只 `import { … } from '@/lib/api'` 或 `'@/lib/api/projects'`；**零** `fetch`、**零** `/api/` 字面量。

### 4.2 Port 接口约定

每个域模块导出 **typed async 函数**，命名与 REST 资源对齐，例如：

```typescript
// agents.ts — 示意
export async function listAgents(): Promise<AgentSummary[]>
export async function getAgentConfig(agentId: string): Promise<AgentConfig>
```

SSE 流式接口返回 `EventSource` 或 async generator，路径模板仅出现在 `lib/api/*` 内。

### 4.3 当前差距（2026-06-14）

| 项 | 现状 | 目标 |
|----|------|------|
| `api.ts` 行数 | 1161 | < 50 或删除 |
| split 模块行数 | 894 | 承接全部域 API |
| pages 直连接 | 0 ✅ | 0 |
| barrel 迁移 | ~30 处仍 import legacy 路径 | 统一 `@/lib/api` index |

---

## 5. 契约集成测试 {#contract-tests}

### 5.1 形状测试（已有）

`test_api_contract.py` — 断言关键响应字段集合（overview、groups、summary、HTTP 错误信封）。

### 5.2 路由 parity 测试（v4 新增）

**目标**：`frontend-v2/src/lib/api/*.ts` 中每个 `hubFetch('…')` / `EventSource('…')` 路径，在 FastAPI `app.routes` 中存在且 HTTP method 一致。

**建议实现**：

1. **FE 侧静态提取**：正则或 TS AST 解析 `` `/api/...` `` 与 `hubFetch` 第一个参数；归一化 `{param}` 模板。
2. **Hub 侧 introspection**：TestClient app from `hub.api.server:app`；收集 `(method, path)` 集合。
3. **匹配规则**：FE 模板 path 匹配 Hub path（忽略 `{agent_id}` vs `{agentId}` 命名差异，统一 normalize）。
4. **CI**：`pytest backend/common/tests/test_fe_hub_route_parity.py -q`

**失败即红**：前端调用了 Hub 未注册的路由，或 method 不一致（如 FE POST / Hub 仅 GET）。

### 5.3 OpenAPI（optional future）

- 生成：`app.openapi()` → `docs/openapi.yaml`（CI artifact，不提交或可选提交）。
- 用途：外部客户端、Mac App 合约对照；**不替代** HUB_API_CONTRACT 中的 SSE 事件与行为章节。
- 触发条件：Wave 5 完成且 arch-gate PASS 后单独任务。

---

## 6. 禁止清单（arch-gate 必检）

| # | 规则 | 检测方式 |
|---|------|----------|
| 1 | frontend 不得 import backend 源码 | `rg 'from.*backend|import.*backend' frontend-v2` |
| 2 | backend 不得 import frontend TS/TSX | `rg 'frontend-v2/src' backend --glob '*.py'`（dist 路径除外） |
| 3 | UI 层不得 `fetch(` | `rg 'fetch\(' frontend-v2/src/pages frontend-v2/src/components` |
| 4 | UI 层不得 `/api/` 字面量 | `rg '/api/' frontend-v2/src/pages frontend-v2/src/components` |
| 5 | 新端点必须更新契约 + 测试 | PR checklist + parity pytest |

---

## 7. 与 v3 的关系

| 维度 | v3 (`myteam-platform-v3`) | v4 (`myteam-architecture-v4`) |
|------|----------------------------|--------------------------------|
| 范围 | 平台能力、token、PG、v2 功能、E2E | FE/BE 模块边界、端口、契约 parity |
| API 拆分 | P2.1 方案 + P3.1 部分执行 | Wave 3–5 完成 + server.py < 400 |
| Store | P2.4 PG 方案 | StoreBackend Protocol 提取 |
| 验收 | platform-v3-final-gate | architecture-v4-gate-record |

**并行**：v4 可在 v3 P3/P4 期间执行；二者 gate **独立签发**，互不替代。

---

## 8. arch-gate 验收清单

- [ ] `server.py` < 400 行
- [ ] `StoreBackend` Protocol + Sqlite 实现 + Store 委托
- [ ] API Wave 3–5 路由已提取
- [ ] `api.ts` < 50 行或已删除；路径仅在 `lib/api/*`
- [ ] pages/components：0 fetch、0 `/api/`
- [ ] `test_api_contract.py` + route parity 测试 100% pass
- [ ] `pytest backend -q` 0 failed
- [ ] HUB_API_CONTRACT.md 与实现一致（人工 diff 或 parity 覆盖）
