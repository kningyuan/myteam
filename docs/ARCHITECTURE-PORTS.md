# 端口化架构（Port Framework）

> 版本：2026-06-14 · 与 [`ARCHITECTURE.md`](./ARCHITECTURE.md) §9 配套  
> 原则：**上层依赖端口契约，不依赖具体实现**（Adapter 包、SQLite、某 CLI 二进制）。

---

## 1. 端口一览

| 端口 | 契约类型 | 定义位置 | 默认实现 | 注册 / 注入 |
|------|----------|----------|----------|-------------|
| **CLIAdapter** | ABC | `backend/adapter/protocol.py` | `OpenCodeAdapter`, `ClaudeCodeAdapter` | `adapter/registry.py` + `adapters/__init__.py` 侧效注册 |
| **StoreBackend** | Protocol（规划中） | [`docs/plans/pg-migration-plan.md`](./plans/pg-migration-plan.md) §3.2 | `Store`（SQLite 门面，~1099 行） | 工厂 `Store()`；PG 后端未落地 |
| **TokenUsageSink** | `@runtime_checkable` Protocol | `backend/common/token_usage.py` | `StoreTokenUsageSink` | `AgentPort(..., token_sink=...)` 构造注入 |
| **AgentPort Transport** | `Callable[[DeliveryContext], None]` | `backend/common/agent_port.py` | `AdapterTransport` | `run_kernel.py` / 测试注入 fake transport |
| **AgentMemoryProvider**（L1 工作记忆） | Protocol | `backend/common/agent_memory.py` | `NativeAgentMemory` | `get_agent_memory_provider()` 字典工厂 |
| **MemoryBackend**（L3 团队 KB） | Protocol | `backend/common/memory.py` | `SqliteMemory` | `get_backend()` + `MEMORY_BACKEND` env |
| **ChatPort**（前端，目标） | TypeScript 模块边界 | `frontend-v2/src/lib/api/chat.ts` | `hubFetch` + SSE helpers | 按域拆分，尚无独立 interface 类型 |
| **ProjectsPort**（前端，目标） | TypeScript 模块边界 | `frontend-v2/src/lib/api/projects.ts` | `hubFetch` 项目 CRUD / 运行 | 同上 |

**说明**

- **StoreBackend**：当前全系统仍直接使用 concrete `Store`；PG 迁移方案已定义 `StoreBackend` Protocol，实施时 `Store` 变为薄门面。
- **ChatPort / ProjectsPort**：前端已按域拆文件（`api/chat.ts`、`api/projects.ts`），语义上即「端口」；后续可抽 `interface ChatPort` 便于 mock，Hub 侧无对应 TS 类型。

---

## 2. 统一模式：Protocol/ABC → Registry 或 DI → 实现

```text
┌─────────────────────────────────────────────────────────────┐
│  契约层   CLIAdapter (ABC)  TokenUsageSink (Protocol)       │
│           Transport (Callable)  AgentMemoryProvider (Protocol)│
└───────────────────────────┬─────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
   Registry 侧效       构造函数 DI         工厂 + env
   adapter/registry    AgentPort(...)      get_agent_memory_provider()
   adapters/__init__   run_kernel 组装     get_backend()
         │                  │                  │
         ▼                  ▼                  ▼
   opencode / claude   AdapterTransport    NativeAgentMemory
   codex / cursor stub StoreTokenUsageSink  SqliteMemory
                       (测试: fake fn)
```

| 模式 | 适用 | 示例 |
|------|------|------|
| **Registry + 导入注册** | 可插拔 CLI 后端、多实例并列 | `registry.register(OpenCodeAdapter())` |
| **构造函数 DI** | 内核单路径、测试需替换 | `AgentPort(transport=..., token_sink=...)` |
| **模块工厂** | 全局策略切换、env 驱动 | `get_agent_memory_provider("native")` |
| **Hub 单例** | 请求级 Store 生命周期 | `hub/api/deps.py` → `we_store()` |

**Adapter 解析顺序**（内核）：`agent_transport._default_adapter()` → `registry.get(backend)` → 回退 `opencode`。Hub 聊天路径：`ChatService` → `registry.get(backend_id)`，不经 `AgentPort`。

---

## 3. 各层如何依赖端口

### System Kernel（`backend/common/`）

| 组件 | 依赖 | 不依赖 |
|------|------|--------|
| `Process` | `Store`, 注入的 `AgentPort` | 具体 CLI、Hub |
| `AgentPort` | `Transport`, `TokenUsageSink`, `Store` | `opencode` / `claude` 包 |
| `AdapterTransport` | `CLIAdapter`（经 registry 或注入） | subprocess 命令行细节（在 adapter 子类） |
| `run_kernel.py` | 组装上述端口 | FastAPI |

单测：`test_agent_port.py`、`test_agent_transport.py` 注入 fake `Transport` / mock adapter，无需真实 CLI。

### Hub（`backend/hub/`）

| 路径 | 端口 | 备注 |
|------|------|------|
| `services/chat_service.py` | `CLIAdapter` via `registry` | SSE 流式聊天 |
| `services/project_launch.py` | `run_kernel` → `AgentPort` | 后台编排 |
| `api/routes/*.py` | `deps.we_store()` → `Store` | 薄路由；P3.1 域拆分 |
| `api/observability_api.py` | `Store` 只读 | 与内核共用真相库 |

Hub **不** import `adapters/opencode` 直接跑 subprocess；经 `base/agent_chat` 或 `ChatService`。

### Frontend（`frontend-v2/`）

| 模块 | 职责 | 对应后端 |
|------|------|----------|
| `lib/api/client.ts` | HTTP/SSE 基座 | — |
| `lib/api/chat.ts` | **ChatPort** 语义 | `/api/chat/*` |
| `lib/api/projects.ts` | **ProjectsPort** 语义 | `/api/projects/*`, `/api/obs/projects` |
| `lib/api/workflows.ts` | workflow CRUD | `/api/workflows/*` |

UI 组件应 import 域模块，避免再膨胀单体 `api.ts`（已 deprecated 重导出 `api/index`）。

---

## 4. 实现状态与占位

| 后端 ID | 状态 | 行为 |
|---------|------|------|
| `opencode` | 生产 | 完整 `SubprocessCLIAdapter` |
| `claude` | 生产 | 完整 `SubprocessCLIAdapter` |
| `codex` | **Stub** | 注册于 registry；`run()` yield `EventKind.ERROR` + `NOT_IMPLEMENTED` |
| `cursor` | **Stub** | 同上 |

Stub 目的：设置页 / `/api/backends` 可列出未来后端，避免 silent fallback；真实 parser 见 [`store-token-adapter-plan.md`](./plans/store-token-adapter-plan.md) §B.4.3–4。

---

## 5. 相关文档

| 文档 | 内容 |
|------|------|
| [ARCHITECTURE.md §9](./ARCHITECTURE.md#9-前后端分工与端口化) | 前后端分工摘要 |
| [FRAMEWORK_BOUNDARY.md](./FRAMEWORK_BOUNDARY.md) | 框架/业务边界 |
| [plans/api-split-plan.md](./plans/api-split-plan.md) | Hub 路由域拆分 |
| [plans/pg-migration-plan.md](./plans/pg-migration-plan.md) | StoreBackend 规划 |
| [plans/store-token-adapter-plan.md](./plans/store-token-adapter-plan.md) | Token + adapter 路线图 |
