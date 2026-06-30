# Adapter CLI 隔离层

`backend/adapter/` 是 myteam 的 **CLI 隔离层**:把 opencode / Claude Code 等外部 CLI 后端收敛到统一抽象,对上游(common 内核、hub 服务)只暴露与 CLI 无关的 `RunRequest` / `AgentEvent` 两份契约。核心不变量见 `docs/ARCHITECTURE.md` §10。

## 模块定位

| 维度 | 说明 |
|------|------|
| **是什么** | CLI 后端适配层:`RunRequest` → 子进程 → 原始 stdout → parser → 统一 `AgentEvent` 流 |
| **不是什么** | 不是编排内核(在 `common/`);不是 Web 服务(在 `hub/`);不持有模型 token(CLI 自带鉴权) |
| **入口** | 上游通过 `adapter.core.registry.registry.get(<id>)` 取实例,调 `.run(request)` 拿 `Generator[AgentEvent]` |
| **真相源** | 无自有持久化;MCP/Skill 同步产物落在各 agent `business/workspaces/workspace-<id>/` |

## 核心不变量(AGENTS.md §10)

1. **唯二跨 CLI 数据契约**:`RunRequest`(入)与 `AgentEvent`(出)。上游只见这两份,不见 CLI 原始输出。
2. **parser.py 是唯一格式耦合处**:`adapters/<cli>/parser.py` 是整个仓库唯一允许知道 CLI 原始 stdout 格式的地方。
3. **服务层零 CLI 耦合**:`hub/services/`、`base/` 不得出现 `opencode`、`claude`、`subprocess` 字样;UI 不得引用 CLI 专有字段(`part.text`、`sessionID`、原始 JSON)。
4. **注册靠 side-effect import**:`adapter/__init__.py` 顶部 `import adapter.<cli>.adapter` 触发各实例 `registry.register(...)`。

## 三层结构

```
adapter/
├── core/         抽象层(与 CLI 无关):events / protocol / registry / sse / subprocess_cli
├── opencode/     OpenCode CLI 实现:adapter / parser / mcp_sync / skill_sync
├── claude/       Claude Code CLI 实现:adapter / parser / mcp_sync / skill_sync
├── __init__.py   side-effect import 触发注册 + re-export 常用符号
├── stub_cli.py   PlannedCLIAdapter 占位(run() 直接 yield ERROR)
└── tests/        10 个测试文件(见 tests/README.md)
```

### 数据流

```
        上游(common.agent.agent_transport / hub.services.chat_service)
                              │
                              │ RunRequest(workspace, message, model, ...)
                              ▼
        ┌──────────────────────────────────────────────────────┐
        │            AdapterRegistry.get(backend_id)            │
        │              → CLIAdapter 实例(opencode/claude)       │
        └──────────────────────────────┬───────────────────────┘
                                       │ request
                                       ▼
        ┌──────────────────────────────────────────────────────┐
        │            SubprocessCLIAdapter.run(request)          │
        │   拼命令行 → Popen(start_new_session=True)            │
        │   → stream_subprocess_io(cancel 看门狗 + stderr 汇总) │
        └──────────────────────────────┬───────────────────────┘
                                       │ 逐行 stdout
                                       ▼
        ┌──────────────────────────────────────────────────────┐
        │   adapters/<cli>/parser.parse_line(line)              │  ← 唯一格式耦合处
        │   原始 NDJSON / stream-json → AgentEvent              │
        └──────────────────────────────┬───────────────────────┘
                                       │ Generator[AgentEvent]
                                       ▼
        ┌──────────────────────────────────────────────────────┐
        │  上游消费:agent_transport 落库 / sse.encode_event     │
        │  → SSE JSON({"event":"thinking",...}) 推 UI           │
        └──────────────────────────────────────────────────────┘
```

## 文件清单

### 根文件

| 文件 | 职责 |
|------|------|
| `__init__.py` | side-effect import 触发 opencode/claude 注册;re-export `AgentEvent`/`EventKind`/`RunRequest`/`CLIAdapter`/`registry`/`encode_*` 等 |
| `stub_cli.py` | `PlannedCLIAdapter`:Registry 可见占位,`run()` 直接 yield `ERROR(NOT_IMPLEMENTED)`,供未接线的后端列出 |

### core/(抽象层,与 CLI 无关,5 文件)

| 文件 | 职责 |
|------|------|
| `events.py` | `EventKind` 枚举(8 种)+ `AgentEvent` dataclass + `to_thinking_payload()` |
| `protocol.py` | `ModelInfo` / `AdapterCapabilities` / `RunRequest` / `CLIAdapter` 抽象基类 |
| `registry.py` | `AdapterRegistry` 单例:`register` / `get` / `list_all` / `list_models_all`;模块级 `registry` |
| `sse.py` | `AgentEvent` → SSE JSON 线协议:`encode_event` / `encode_error` / `encode_done` / `encode_citations` |
| `subprocess_cli.py` | `SubprocessCLIAdapter` 基类:进程组回收 + `stream_subprocess_io` + cancel 看门狗 |

详见 [`core/README.md`](./core/README.md)。

### opencode/(OpenCode CLI 实现,4 文件)

| 文件 | 职责 |
|------|------|
| `adapter.py` | `OpenCodeAdapter`(id=opencode,capabilities 全开);命令行构建 + env 注入;末尾 `registry.register` |
| `parser.py` | OpenCode NDJSON → `AgentEvent`(唯一 opencode 格式耦合处) |
| `mcp_sync.py` | 写 `workspace/opencode.json` 的 `mcp` 块(local→command+environment,remote→type+url+headers) |
| `skill_sync.py` | 软链到 `workspace/.opencode/skills/<id>/` |

详见 [`opencode/README.md`](./opencode/README.md)。

### claude/(Claude Code CLI 实现,4 文件)

| 文件 | 职责 |
|------|------|
| `adapter.py` | `ClaudeCodeAdapter`(id=claude,capabilities 全开);CLI 探测 + 命令行构建;末尾 `registry.register` |
| `parser.py` | Claude stream-json → `AgentEvent`(唯一 claude 格式耦合处,6 种行格式) |
| `mcp_sync.py` | 写 `workspace/.mcp.json` 的 `mcpServers` 块(local→command+args+env,remote→type:http+url+headers) |
| `skill_sync.py` | 软链到 `workspace/.claude/skills/<id>/` |

详见 [`claude/README.md`](./claude/README.md)。

## 核心契约

### RunRequest(`core/protocol.py`)

一次 Agent 运行请求,与 CLI 无关:

| 字段 | 类型 | 说明 |
|------|------|------|
| `workspace` | `str` | 工作目录(= agent workspace) |
| `message` | `str` | 写入子进程 stdin 的 prompt |
| `model` | `str` | 模型 id(opencode `opencode/xxx`;claude `sonnet`/`claude-sonnet-4-6` 等) |
| `session_id` | `Optional[str]` | 会话续接 id |
| `rules_file` | `Optional[str]` | 合并后的规则文件路径(opencode `-f`;claude `--append-system-prompt-file`) |
| `agent_id` | `Optional[str]` | 触发 env 注入(`OPENCLAW_WORKER_AGENT_ID`)与严格 skill 加载 |
| `cancel_event` | `Optional[Event]` | 置位后看门狗杀进程组 |
| `extra` | `dict` | 扩展(如 `dispatch_token` → `DISPATCH_TOKEN_ENV`) |

### AgentEvent / EventKind(`core/events.py`)

一次 `run()` 产出的统一事件,`kind` 取 `EventKind` 8 种之一:

| EventKind | 含义 | 典型 data |
|-----------|------|-----------|
| `STEP_START` | 一轮开始 | `{}` |
| `TEXT` | 文本输出 | `{content}` |
| `REASONING` | 思考摘要 | `{content}` |
| `TOOL_USE` | 工具调用 | `{name, input, output?, status?}` |
| `TOOL_RESULT` | 工具返回(opencode 独有) | `{content}` |
| `STEP_FINISH` | 一轮结束 | `{reason, tokens{input,output,total,...}}` |
| `ERROR` | 错误 | `{message, ...}` |
| `SESSION` | 会话信息 | `{session_id, model?}` |

`to_thinking_payload()` 把除 `SESSION`/`ERROR` 外的事件转为 SSE `thinking.data`(`{type, ...data}`)。

### parser 隔离边界

- `adapters/<cli>/parser.py` 是**唯一**允许 `json.loads` CLI 原始 stdout 的地方。
- 上游(`agent_transport`、`chat_service`)只迭代 `AgentEvent`,不触碰原始行。
- 新增行格式 → 改对应 `parser.py`;新增事件语义 → 改 `core/events.py` 的 `EventKind`(全 CLI 共享)。

### 注册机制(side-effect)

`adapter/__init__.py` 顶部:

```python
import adapter.opencode.adapter   # 末尾 registry.register(OpenCodeAdapter())
import adapter.claude.adapter     # 末尾 registry.register(ClaudeCodeAdapter())
```

故 `import adapter` 即完成全部注册。上游取实例:`registry.get("opencode")` / `registry.get("claude")`。

## 与其他 backend/ 模块的边界

| 模块 | 关系 | 边界规则 |
|------|------|----------|
| `common/` | common 通过 `common.agent.agent_transport` 调用 adapter | common 只见 `RunRequest` / `AgentEvent`,不见 CLI 原始输出;`agent_transport._default_adapter()` 决定默认后端 |
| `hub/` | `hub.services.chat_service` 直接 import adapter | chat 流(人↔agent)与 kernel 流共用同一 adapter;hub 不绕过 parser |
| `base/` | base 不直接接触 adapter | `base/agent_chat.py` 调 `common.agent.agent_registry`,再经 transport 进 adapter;反向禁止 |
| `config_store/` | adapter 读 `system_config` 取 cli_path / models | adapter 不写 `config/`;CLI 路径优先级见各 adapter 的 `_cli_path()` |
| `common.mcp_catalog` | opencode/claude 的 `mcp_sync` 调 `load_mcp_registry()` | MCP 源在 `business/config/mcp_registry.json`,adapter 只做格式转换 + 落 workspace |

## 新增 CLI 后端的步骤

1. 新建 `adapters/<cli>/` 目录,含 `__init__.py`。
2. 写 `parser.py`:实现 `parse_line(line: str) -> list[AgentEvent]`(唯一格式耦合处)。
3. 写 `adapter.py`:继承 `SubprocessCLIAdapter`,实现 `id` / `display_name` / `capabilities` / `list_models` / `get_default_model` / `run`;**文件末尾** `registry.register(<YourAdapter>())`。
4. (可选)`mcp_sync.py` / `skill_sync.py`:若该 CLI 有原生 MCP/Skill 注册表,实现 `sync_workspace_mcp` / `sync_workspace_skills`,并在 adapter 里覆盖 `sync_agent_mcp` / `sync_agent_skills`。
5. 在 `adapter/__init__.py` 顶部加 `import adapter.<cli>.adapter`(触发注册)。
6. 更新 `common.agent.agent_transport._default_adapter()` 的默认/回退逻辑;`run_kernel.py --backend <cli>` 与 `agents_config.json` 的 per-agent backend 即可生效。
7. 补 `tests/test_<cli>_parser.py` + `test_<cli>_adapter.py`(参照 opencode/claude 测试)。

> 新增 CLI **不需要**改 UI、不改 `core/`、不改上游服务层——这正是隔离层的意义。

## 测试

```bash
PYTHONPATH=backend python3 -m pytest backend/adapter/tests/ -q
```

- 10 个测试文件,42 个用例,全部不依赖外部 CLI(opencode/claude 未安装亦可跑)。
- 用 `tmp_path` 隔离工作区,`monkeypatch` 替换 `load_mcp_registry` / `subprocess.run` / cli 探测。
- 详见 [`tests/README.md`](./tests/README.md)。

## 变更维护

- **新增 CLI**:按上方「新增 CLI 后端的步骤」;更新本 README 文件清单 + 新建 `adapters/<cli>/README.md` + `tests/README.md` 测试清单。
- **新增 EventKind**:改 `core/events.py`;同步所有 `parser.py` 可能产出的新 kind;补 `tests/` 断言。
- **改 RunRequest 字段**:改 `core/protocol.py`;检查所有 adapter 的 `run()` 是否消费;上游 `agent_transport` / `chat_service` 同步。
- **改 parser 行格式**:只动对应 `adapters/<cli>/parser.py`;补/改对应 `test_<cli>_parser.py`。
- **删除/重命名文件**:同步本 README 文件清单 + 对应子目录 README + `tests/README.md` 清单。
- **功能变更**:重跑 `backend/adapter/tests/` 全量,确保零回归。
