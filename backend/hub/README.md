# Hub Web 表现层 + 服务层

myteam 的 Web Hub(`backend/hub/`),是 **A 流程**(人 ↔ Agent 对话 / 群聊 / 项目可观测)的 HTTP 入口,同时承担 **项目后台调度** 的胶水逻辑。它把 FastAPI 薄路由与业务服务拆成两层,自身不含编排内核状态机。

## 整体职责

| 维度 | 说明 |
|------|------|
| **是什么** | Web Hub 表现层 + 服务层:对话 / Agent 管理 / 群组 / 可观测的 HTTP 入口,以及项目后台调度桥接 |
| **不是什么** | 不是编排内核(在 `common/`);不是 CLI 适配层(在 `adapter/`);不是配置存储(在 `config_store/`);不持久化任务真相(在 `common/store/`) |
| **入口** | `hub/api/server.py`(`./run.sh start` → uvicorn 绑定 `0.0.0.0:8765` → `/v2/`) |
| **真相源** | 只读消费 `common/store/` 的 SQLite;自身运行态写在 `Store project.meta.hub_kernel_run` |

## 两层结构

`hub/` 拆为 `api/`(FastAPI 薄路由)与 `services/`(业务服务)两个子包,`hub/__init__.py` 为空(仅包标识)。两层职责正交:api 只做参数解析 / 路由 / 错误信封,业务逻辑下沉到 services 与 `base/`。

```
                         浏览器 (frontend/ build → /v2/)
                                    │ HTTP / SSE
                                    ▼
┌──────────────────────────────────────────────────────────────┐
│                       hub/api/  (薄路由层)                     │
│  server.py: lifespan(启动恢复) + CORS + 路由挂载 + 异常信封 + SPA │
│     ├─ *_api.py (11 个直接文件:skills/mcp/rules/preferences…)  │
│     └─ routes/  (10 个域路由: agents/chat/groups/projects…)    │
└──────────────────────────────┬───────────────────────────────┘
                               │ 调用
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                  hub/services/  (业务服务层)                   │
│  chat_service  ── 编排 Agent 身份/规则/Session → adapter        │
│  sse_bridge / chat_cancel ── 同步 generator → FastAPI SSE + 取消 │
│  stream_fanout → agent_broadcast / group_broadcast ── pub/sub  │
│  project_launch / kernel_run / project_hooks / group_service   │
│        └─ 后台线程调 common.runtime.run_kernel                   │
└──────────────────────────────┬───────────────────────────────┘
                               │ RunRequest / AgentEvent
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  base/ (agent_chat/agent_identity) ── adapter/ (CLI 隔离层)    │
│                                          │                    │
│  common/ (store / runtime / agent) ◀─────┘  只读 SQLite        │
└──────────────────────────────────────────────────────────────┘
```

**A 流程(对话 / 群聊,流式):** 前端 → `api/routes/chat` → `services/sse_bridge` + `chat_cancel`(流式桥接 + 取消)→ `chat_service.stream`(组装 system_prompt + 调 `adapter.run`)→ SSE → `stream_fanout` → `agent_broadcast` / `group_broadcast`(pub/sub 推已打开 Tab)。

**B 流程(项目后台调度,批处理):** `api/routes/projects` → `services/project_launch`(后台线程跑 `common.runtime.run_kernel`)→ `kernel_run`(运行态写 Store meta)→ `project_hooks`(自动建群 + 进度通报)→ `project_group_service`。

## 文件清单

完整职责见各子包 README,此处给出一页式速查。`hub/__init__.py` 为空(仅包标识)。

### api/ 薄路由层(11 个直接文件 + routes/ 10 个域文件)

直接文件(api/ 根目录,含 `server.py` 装配中心):

| 文件 | 职责 |
|------|------|
| `server.py` | FastAPI app 装配:lifespan 启动恢复 + CORS + 路由挂载 + 异常信封 + SPA 托管 |
| `deps.py` | 共享依赖:`we_store()` 返回 `Store` 单例 |
| `errors.py` | 统一错误类型 `APIError`(code/message/hint/doc_url/status_code)+ `to_dict` 信封 |
| `config_api.py` | Phase4 配置 API:5 子路由(kb 模板 / task_type_skills / preference_sections / workflow_profile / agent_task_type_rules) |
| `observability_api.py` | 只读可观测路由(D17):项目 / cost / events / fleet / 任务 / interaction / SSE |
| `skills_api.py` | Skill 库 / 草案 / 分组 / 分类 CRUD + pending 审批 + 删除联动 agent_registry |
| `rules_api.py` | 团队通用 rules 文件 list / 读 / 写 |
| `mcp_api.py` | MCP server 库 CRUD + enabled patch + 删除联动 agent_registry |
| `preferences_api.py` | 全局 `USER.md` 读 / 写 + 同步到所有 agent |
| `prompt_injections_api.py` | 注入块 CRUD |
| `prompt_templates_api.py` | kinds + task_types 两层模板 CRUD |
| `delivery_profiles_api.py` | 交付 profile list / create / update / delete |

> 注:直接文件含 `server.py` / `deps.py` / `errors.py` 三个非路由文件 + 8 个 `*_api.py` 路由文件,共 11 个。

域路由(`routes/`,由 `routes/__init__.py` 聚合为 `api_router` 一次性挂载):

| 文件 | 前缀 | 职责 |
|------|------|------|
| `agents.py` | `/api/agents`(+ obs 无前缀) | Agent 列表 / 详情 / workspace 编辑 / 删除 / manage / notify / events SSE / create / suggest-id / registry CRUD |
| `chat.py` | `/api/chat` | 1-on-1 流式对话 / cancel / status / messages 历史 / clear / archive |
| `config.py` | `/api/agents/{id}/config` 等 | agent backend/model 配置 / apply-model-to-all / backends 列表 / system config / skill config / sync |
| `groups.py` | `/api/groups` + `/api/projects` | 群 CRUD / 成员 / 圆桌 / 群聊 SSE;项目建群 |
| `projects.py` | `/api/projects`(+ `_extra_router`) | 项目列表 / 详情 / 日志 / run / run-status / dispatch / resume / deliverable / cancel / delete |
| `single_execute.py` | `/api/single-execute` | 单 Agent execute:list / get / prepare / finish |
| `system.py` | `/api/status` | 初始化状态 / 项目数 / 运行中数 / token 趋势 |
| `task_types.py` | `/api/task-types` | 任务类型注册表:list / outcome-kinds / suggest / CRUD |
| `workflows.py` | `/api/workflows` | workflow list / suggest / get / CRUD |
| `delivery_templates.py` | `/api/delivery-templates` | 交付模板 list / get / CRUD |

### services/ 业务服务层(15 个文件)

| 文件 | 职责 | 关键类 / 函数 |
|------|------|---------------|
| `agent_broadcast.py` | Agent 实时事件广播(pub/sub,每 agent 一组 `asyncio.Queue(maxsize=300)`) | `subscribe` / `unsubscribe` / `publish` |
| `group_broadcast.py` | 项目群实时事件广播(与 agent_broadcast 对称,按 group_id) | `subscribe` / `unsubscribe` / `publish` |
| `chat_cancel.py` | 活跃对话流取消注册表(客户端 abort 或显式 /cancel 终止底层 CLI) | `ChatCancelRegistry` / `CombinedCancel` / `wrap_producer` / `wrap_producer_background` |
| `chat_archive.py` | 对话归档(隐藏 / 恢复 / 检索) | `hide_chat` / `restore_chat` / `list_hidden` / `search_archives` |
| `chat_service.py` | 对话服务编排(`ChatService.stream` 是 1-on-1 对话唯一入口) | `ChatService.stream` |
| `stream_fanout.py` | `stream_chat` SSE → `agent_thinking` 并广播到群组 / Agent Tab | `sse_to_thinking` / `fanout_stream_event` |
| `sse_bridge.py` | 同步 SSE 生成器 → FastAPI 桥接(客户端断开时取消或后台继续) | `stream_with_cancel` / `stream_background_on_disconnect` |
| `kernel_run.py` | Hub kernel 运行态(仅存 `Store project.meta.hub_kernel_run`) | `_set/_get/_is/_clear_kernel_run` / `_reconcile_stale_kernel_runs` |
| `project_launch.py` | 项目发起与后台内核调度 | `persist_project_launch` / `run_kernel_bg` / `resume_kernel_bg` / `start_kernel_job` |
| `project_hooks.py` | Hub 默认 `ProjectHooks`(自动建群 + 群进度通报 + loop 群讨论) | `hub_project_hooks` / `_on_wave` |
| `project_group_service.py` | 项目协作群 | `setup_project_group` / `post_project_progress` / `format_progress_message` |
| `project_service.py` | 项目服务(优先 SQLite Store,降级 task_data.json) | `list_projects` / `get_project` / `get_project_log` |
| `notify_service.py` | 同步 / 异步通知投递 | `notify_agent_sync` / `notify_via_project_group` |
| `single_execute_service.py` | 单 Agent execute 服务 | `list_single_execute_projects` / `prepare_single_execute` / `finish_single_execute` |
| `agent_registry.py` | Agent 注册表(读 `agents_registry.json` + 扫 workspace) | `get_agents_registry` / `register_agent` / `sync_missing_agent_skills` |

> 注:`agent_registry.py` 属配置 / 注册表读写服务,与对话 / 调度链解耦,单列为第 15 个文件。

## 与其他 backend/ 模块的边界

hub 是依赖链的**末端消费者**,不反向被任何 backend 模块依赖。

| 模块 | 关系 | 边界规则 |
|------|------|----------|
| `common/` | hub 依赖 common(最重) | `services/kernel_run` 调 `common.runtime.run_kernel`;`api/observability_api` 只读 common 的 SQLite;`services/project_*` 读 `common.store` / `common.project` |
| `base/` | hub 依赖 base | `services/chat_service` 调 `base.agent_chat`(Adapter 唯一入口);`server.py` 调 `base.agent_factory`;hub 不绕过 base 直接碰 CLI |
| `config_store/` | hub 依赖 | `server.py` 读 `system_config`;`chat_service` 用 `sessions` |
| `adapter/` | hub 间接依赖(经 base) | 唯一直接接触 CLI 抽象的层在 `base/agent_chat`;hub 服务层只见 `RunRequest` / `AgentEvent`(D10 隔离) |
| `memstack/` | hub 惰性依赖 | 经 `base/` 间接调用,不直接 import |
| `execution_harness/` | hub 惰性依赖 | 经 `common/` 间接调用,不直接 import |

**反向禁止**:common / base / adapter / config_store / memstack / execution_harness 均不得 import `hub.*`。

## 子包文档

- 薄路由层详见 [`api/README.md`](./api/README.md)
- 业务服务层详见 [`services/README.md`](./services/README.md)

## 测试

hub 仅有 `services/tests/` 一个测试目录,聚焦**可独立测试的纯逻辑服务**(不依赖外部 CLI、不启动真实服务器):

```bash
PYTHONPATH=backend python3 -m pytest backend/hub/services/tests/ -q
```

覆盖范围(5 个测试文件,48 个用例):
- `test_stream_fanout.py` — SSE → thinking 广播、raw 事件丢弃、adapter 隔离断言
- `test_agent_broadcast.py` — Agent pub/sub:subscribe / publish / 多订阅者 / 满队列(maxsize=300)自动剔除 / unsubscribe 后不收 / 空 id 短路
- `test_group_broadcast.py` — 群 pub/sub(与 agent_broadcast 对称,按 group_id):subscribe / publish / 多订阅者 / 满队列剔除 / group 隔离
- `test_chat_cancel.py` — `ChatCancelRegistry`(register / cancel / unregister / 同 key 抢占)+ `CombinedCancel`(合并 SSE 断开 + 显式 /cancel)+ `wrap_producer` / `wrap_producer_background`
- `test_errors.py` — `APIError` 构造 / 默认值 / `to_dict()` 统一 error 信封(测 `hub/api/errors.py`)

**不测**(本轮聚焦纯逻辑可隔离服务):`chat_service` / `stream_chat`(需 adapter + CLI)、`project_launch`(需 kernel)、`notify_service`(需 `stream_chat`)、`sse_bridge`(需 FastAPI Request)——这些走端到端集成测试(`common/tests/`)间接覆盖;`kernel_run`(需 mock Store)、`chat_archive`(待补单测)同理暂由集成测试覆盖。

## 变更维护

- **新增 API 路由**:直接文件放进 `api/` 并在 `server.py` `include_router`;域路由放进 `api/routes/` 并在 `routes/__init__.py` 聚合;同步更新 `api/README.md` 清单表
- **新增业务服务**:放进 `services/`,如可独立测试则在 `services/tests/` 补测试;更新 `services/README.md` 清单表与本 README 的两层结构图
- **新增可测服务**:遵循现有约束——`tmp_path` 隔离、`monkeypatch` mock Store、不依赖 CLI、不启动服务器
- **删除 / 重命名文件**:同步更新三份 README 的清单表
- **功能变更**:重跑 `services/tests/`,确保零回归
