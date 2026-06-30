# Hub 业务服务层

`backend/hub/services/` 是 Hub 的业务服务层:承载对话编排、流式桥接、实时广播、对话归档、项目后台调度等业务逻辑。路由层(`hub/api/`)只做参数解析与错误信封,真正干活的是这里的 15 个服务文件。

## 文件清单(15 个)

| 文件 | 职责 | 关键类 / 函数 |
|------|------|---------------|
| `agent_broadcast.py` | Agent 实时事件广播(pub/sub,每 agent 一组 `asyncio.Queue(maxsize=300)`) | `subscribe` / `unsubscribe` / `publish` |
| `group_broadcast.py` | 项目群实时事件广播(与 agent_broadcast 对称,按 group_id) | `subscribe` / `unsubscribe` / `publish` |
| `chat_cancel.py` | 活跃对话流取消注册表(客户端 abort 或显式 /cancel 终止底层 CLI) | `ChatCancelRegistry` / `CombinedCancel` / `register_chat` / `cancel_chat` / `wrap_producer` / `wrap_producer_background` |
| `chat_archive.py` | 对话归档(隐藏 / 恢复 / 检索,基于 `CHAT_ARCHIVES_DIR/index.json` + 快照) | `hide_chat` / `restore_chat` / `list_hidden` / `search_archives` / `is_hidden` |
| `chat_service.py` | 对话服务编排(`ChatService.stream` 是 1-on-1 对话唯一入口) | `ChatService.stream` |
| `stream_fanout.py` | `stream_chat` SSE → `agent_thinking` 并广播到群组 / Agent Tab | `sse_to_thinking` / `fanout_stream_event` |
| `sse_bridge.py` | 同步 SSE 生成器 → FastAPI 桥接(客户端断开时取消或后台继续) | `stream_with_cancel` / `stream_background_on_disconnect` |
| `kernel_run.py` | Hub kernel 运行态(仅存 `Store project.meta.hub_kernel_run`) | `_set_kernel_run` / `_get_kernel_run` / `_is_kernel_running` / `_clear_kernel_run` / `_reconcile_stale_kernel_runs` |
| `project_launch.py` | 项目发起与后台内核调度 | `persist_project_launch` / `run_kernel_bg` / `resume_kernel_bg` / `start_kernel_job` |
| `project_hooks.py` | Hub 默认 `ProjectHooks`(自动建群 + 群进度通报 + loop 群讨论) | `hub_project_hooks` / `_on_wave` |
| `project_group_service.py` | 项目协作群 | `setup_project_group` / `post_project_progress` / `format_progress_message` |
| `project_service.py` | 项目服务(优先 SQLite Store) | `list_projects` / `get_project` / `get_project_log` |
| `notify_service.py` | 同步通知(供 team-ok bridge 调用) | `notify_agent_sync` / `notify_via_project_group` / `_collect_text_and_write_file` |
| `single_execute_service.py` | 单 Agent execute 服务 | `list_single_execute_projects` / `get_single_execute_task` / `prepare_single_execute` / `finish_single_execute` |
| `agent_registry.py` | Agent 注册表(读 `agents_registry.json` + 扫 workspace) | `get_agents_registry` / `format_registry_for_prompt` / `register_agent` / `sync_missing_agent_skills` |

> 注:`agent_registry.py` 属配置 / 注册表读写服务,与对话 / 调度链解耦,单列为第 15 个文件。

## 内部协作链

### 流式对话链(A 流程)

```
hub/api/routes/chat.py
   │
   ▼
sse_bridge.stream_with_cancel ──┐  同步 generator → FastAPI AsyncIterator
chat_cancel.wrap_producer ───────┤  SSE 断开 + 显式 /cancel 合并为单一 cancel 源
   │                             │
   ▼                             │
chat_service.ChatService.stream  │  组装 system_prompt + merge rules → adapter.run
   │                             │
   ▼  SSE (thinking/text/done)   │
stream_fanout.fanout_stream_event│  只认 thinking 等标准化事件(adapter 隔离)
   │                             │
   ├─▶ agent_broadcast.publish ──┤  → Agent 私聊 Tab(pub/sub)
   └─▶ group_broadcast.publish ──┘  → 项目群 Tab(pub/sub)
```

### 项目后台调度链(B 流程)

```
hub/api/routes/projects.py
   │
   ▼
project_launch.persist_project_launch / run_kernel_bg
   │  后台线程
   ▼
common.runtime.run_kernel ──┐  (编排内核,不在 hub)
   │                        │
   ▼  hooks                 │
project_hooks.hub_project_hooks ── on_team_ready / on_task_done / on_wave
   │                        │
   ▼                        │
project_group_service.setup_project_group / post_project_progress
   │  自动建群 + 进度通报      │
   │                        │
kernel_run._set_kernel_run ◀┘  运行态写 Store project.meta.hub_kernel_run
   │
   ▼  Hub 重启时
kernel_run._reconcile_stale_kernel_runs  清除残留 running=true
```

`notify_service` 是 team-ok bridge 的旁路:经 `stream_chat` 收集 Agent 文本回复并写 `.response` 文件,同时经 `stream_fanout` 推私聊 SSE。

## 与 api/ 和 base/ 的调用关系

services 是**被 api/ 调用、自身调 base/ 与 common/** 的中间层,不反向被 base/ 调用。

| 方向 | 调用方 → 被调方 | 说明 |
|------|----------------|------|
| **api → services** | `routes/chat.py` → `sse_bridge` + `chat_cancel` + `chat_service` | 对话流式入口:桥接 + 取消 + 编排 |
| | `routes/chat.py` / `routes/groups.py` → `chat_archive` | 对话归档(隐藏 / 恢复) |
| | `routes/projects.py` → `project_launch` + `project_service` + `kernel_run` | 项目发起 / 列表 / 运行态 |
| | `routes/single_execute.py` → `single_execute_service` | 单 Agent execute |
| | `routes/agents.py` → `agent_registry` | Agent 注册表读写 |
| | `skills_api` / `mcp_api` 删除联动 → `agent_registry` | 删 Skill/MCP 时同步 registry |
| **services → base** | `chat_service` → `base.agent_chat` | **Adapter 唯一入口**(D10 隔离):hub 不绕过 base 直接碰 CLI |
| | `chat_service` → `base.agent_identity` | 组装 system_prompt / 身份 |
| **services → common** | `project_launch` → `common.runtime.run_kernel` | 后台线程跑编排内核 |
| | `kernel_run` → `common.store.Store` | 运行态写 `project.meta.hub_kernel_run` |
| | `project_service` → `common.store` / `common.project` | 项目列表 / 详情(只读) |
| | `notify_service` → `common.agent` 间接 | 经 `stream_chat` 收集回复 |

**边界规则**:services 不直接 `subprocess`、不直接 import `adapter` 的 parser、不触碰 CLI 原始输出(D10);经 `base/` 间接消费 `RunRequest` / `AgentEvent`。`base/` 与 `common/` 均不反向 import `hub.services.*`。

## 测试

测试在 `services/tests/`,只覆盖**可独立测试的纯逻辑服务**(不依赖外部 CLI、不启动真实服务器):

```bash
PYTHONPATH=backend python3 -m pytest backend/hub/services/tests/ -q
```

| 测试文件 | 覆盖服务 | 覆盖点 |
|----------|----------|--------|
| `test_stream_fanout.py` | `stream_fanout` | SSE → thinking 广播、raw 事件丢弃、adapter 隔离断言 |
| `test_agent_broadcast.py` | `agent_broadcast` | subscribe / unsubscribe / publish、多订阅者、满队列(maxsize=300)自动剔除、unsubscribe 后不收、空 id 短路 |
| `test_group_broadcast.py` | `group_broadcast` | subscribe / unsubscribe / publish、多订阅者、满队列剔除、group 隔离(与 agent_broadcast 对称) |
| `test_chat_cancel.py` | `chat_cancel` | `ChatCancelRegistry` register / cancel / unregister / 同 key 抢占、`CombinedCancel` 合并 cancel、`wrap_producer` / `wrap_producer_background` |
| `test_errors.py` | `hub/api/errors` | `APIError` 构造 / 默认值 / `to_dict()` 统一 error 信封(测 `api/errors.py`,放在本目录统一跑) |

**不测**:`chat_service`(需 adapter + CLI)、`project_launch`(需 kernel)、`notify_service`(需 `stream_chat`)、`sse_bridge`(需 FastAPI Request)——这些走端到端集成测试(`common/tests/`);`kernel_run`(需 mock Store)、`chat_archive`(待补单测)暂由集成测试间接覆盖。

## 变更维护

- **新增业务服务**:放进 `services/`;如可独立测试则补 `tests/test_*.py`;更新本 README 文件清单表与协作链图
- **新增可测服务**:遵循现有约束——`tmp_path` 隔离、`monkeypatch` mock Store、不依赖 CLI、不启动服务器
- **修改流式 / 调度链**:同步更新本 README 的两张协作链图
- **删除 / 重命名文件**:同步更新本 README 文件清单表与 `hub/README.md` 的结构图
