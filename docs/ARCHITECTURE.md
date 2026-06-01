# myteam 模块化架构设计

> 目标：轻量级 **UI + 服务 + CLI Adapter**，替代 Telegram + OpenClaw + OpenCode 重型栈  
> 原则：**抽象交互流** 与 **具体 CLI 实例** 分离，OpenCode 先落地，Claude Code 等后扩展

---

## 1. 定位

```
旧栈                          新栈 (myteam)
─────────────────────────────────────────────────────
Telegram 聊天 UI        →     static/ Web UI
OpenClaw 路由/会话      →     hub/ 服务层 + store/
OpenCode CLI            →     adapters/opencode/
(未来) Claude Code CLI  →     adapters/claude/
```

**Adapter 层**负责：把各 CLI 的 NDJSON/stdout **统一**成同一种 **Agent 流式事件**，UI 只认这一种协议。

---

## 2. 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│  UI Layer          static/                                   │
│  消费 SSE：thinking | error | done                           │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP/SSE
┌───────────────────────────▼─────────────────────────────────┐
│  API Layer         hub/api/                                   │
│  FastAPI 路由，不含业务逻辑                                     │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  Service Layer     hub/services/                              │
│  ChatService / AgentService / GroupService                    │
│  编排：身份 + 规则 + Session + Adapter.run()                   │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  Adapter Layer ★   adapter/                                   │
│  协议定义、事件模型、Registry、SessionStore、SSE 编码           │
│  **与具体 CLI 无关**                                            │
└───────────────────────────┬─────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ adapters/   │    │ adapters/   │    │ adapters/   │
│ opencode/   │    │ claude/     │    │ (future)    │
│ Parser+Run  │    │ (stub)      │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
         │                  │                  │
         └──────────────────┴──────────────────┘
                            │ subprocess
                     OpenCode / Claude CLI ...

┌─────────────────────────────────────────────────────────────┐
│  Agent Domain      agents/                                    │
│  workspace 扫描、IDENTITY、规则合并、Factory                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Store Layer       store/                                     │
│  agents_config / groups / sessions / system_config (JSON)     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Orchestration (Phase 2)  skill/team-ok/                      │
│  项目任务状态机；通过 ChatService 调 Agent，不直连 CLI          │
│  逐步去掉 ~/.openclaw 硬编码路径                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 核心抽象：Agent 流式事件

一次用户消息 → Adapter.run() → 事件流。  
**一个完整块** = `step_start` … `step_finish` 之间的所有事件。

### 3.1 统一事件类型 (`adapter/events.py`)

| kind | 含义 | data 字段 |
|------|------|-----------|
| `step_start` | 一步开始 | `{}` |
| `text` | 模型文本（可多次，流式拼接） | `content: str` |
| `tool_use` | 调用工具 | `name, input` |
| `tool_result` | 工具返回 | `content` |
| `step_finish` | 一步结束 | `tokens: {input, output, total, reasoning?}, reason?` |
| `error` | 错误 | `message` |
| `session` | 会话 ID（内部） | `session_id` |

### 3.2 SSE 线协议（UI 消费，短期不变）

```json
{"event":"thinking","data":{"type":"text","content":"..."}}
{"event":"thinking","data":{"type":"tool_use","name":"Read","input":"{...}"}}
{"event":"thinking","data":{"type":"step_finish","tokens":{"input":100,"output":50,"total":150}}}
{"event":"done","data":{"session_id":"ses_xxx"}}
{"event":"error","data":{"message":"..."}}
```

UI **只依赖 `thinking` 的 type**，不依赖 OpenCode 原始 JSON。

### 3.3 Adapter 接口 (`adapter/protocol.py`)

```python
class CLIAdapter(Protocol):
    @property
    def id(self) -> str: ...           # "opencode" | "claude"
    @property
    def display_name(self) -> str: ...

    def list_models(self) -> list[ModelInfo]: ...
    def capabilities(self) -> AdapterCapabilities: ...

    def run(self, request: RunRequest) -> Iterator[AgentEvent]:
        """
        request:
          workspace, message, model, session_id?, rules_file?, agent_id?
        yields:
          AgentEvent (统一事件，已由 Parser 转换)
        """
```

**RunRequest** 与 **AgentEvent** 是跨 CLI 的唯二数据契约。

---

## 4. OpenCode 实例 (`adapters/opencode/`)

```
adapters/opencode/
├── adapter.py      # CLIAdapter 实现：subprocess opencode run
├── parser.py       # 单行 NDJSON → List[AgentEvent]
└── config.py       # cli_path, timeout（读 store/system_config）
```

**Parser 职责**（与 OpenCode 耦合集中在此）：

| OpenCode `type` | → AgentEvent |
|-----------------|--------------|
| `step_start` | `step_start` |
| `text` | `text` ← `part.text` |
| `tool_use` | `tool_use` ← `part.tool`, `part.state.input` |
| `tool_result` | `tool_result` |
| `step_finish` | `step_finish` ← `part.tokens` |
| 其他 | 可选 `debug` 或忽略 |

新增 CLI = 新目录 + 新 Parser + `registry.register()`。

---

## 5. 目录结构（当前）

```
myteam/                          # 工程：平台代码
├── run.sh                       # 启动；export MYTEAM_TEAM_DIR
├── static/                      # 前端 Web UI
├── base/                        # 领域逻辑（agent_chat, factory, groups）
├── hub/
│   ├── api/server.py            # FastAPI 入口
│   └── services/                # chat_service, sse_bridge
├── adapter/ + adapters/         # 适配器抽象 + CLI 实例
├── store/                       # JSON 持久化读写
└── data/                        # 运行态 JSON（gitignore）

~/team/                          # 业务：Agent 团队资产（MYTEAM_TEAM_DIR）
├── workspaces/                  # workspace-{agent_id}
└── skill/                       # universal-rules + team-ok
```

`hub/paths.py` 定义全部路径；业务目录与工程分离，默认 `MYTEAM_TEAM_DIR=~/team`。

---

## 6. 数据流（1-on-1 对话）

```
用户输入
  → ChatService.stream(agent_id, message)
      → 加载 workspace / identity / rules
      → SessionStore.get(session_key)
      → registry.get("opencode").run(RunRequest(...))
          → OpenCodeAdapter: subprocess
          → OpenCodeParser: NDJSON → AgentEvent*
      → SessionStore.set(session_id)
      → sse.encode(event) → SSE 推前端
  → UI: step 块渲染（text 展开，tool 折叠）
```

**GroupService** 同样走 `ChatService.stream`，只做 @mention 路由与消息持久化。

---

## 7. 与 team-ok 的关系（Phase 2）

| 现在 | 目标 |
|------|------|
| team-ok 调 `openclaw agent` | 调 `ChatService` 或 Adapter 直接 |
| 路径 `~/.openclaw/...` | 统一 `myteam/workspaces/` + `myteam/data/` |
| Telegram 通知 | Web UI 通知 / 可选 webhook |
| executor 状态机 | 保留，作为 `orchestration/` 独立模块 |

team-ok **不应**解析 OpenCode JSON；只消费 **AgentEvent 摘要**或最终 text。

> 注：编排层已从 `skill/team-ok/` 的 `executor`/`continuous-executor` 双引擎迁移到
> `skill/team/` 的单一 **Process 内核**（见 §11）。旧引擎已删除，入口统一为 `run_kernel.py`。

---

## 8. 扩展新 CLI（以 Claude Code 为例）

1. 实现 `adapters/claude/parser.py`（Claude stdout → AgentEvent）
2. 实现 `adapters/claude/adapter.py`（`claude` CLI 参数）
3. `registry.register(ClaudeAdapter())`
4. `store/system_config.json` 增加 `backends.claude`
5. UI 后端列表自动从 registry 读取

**无需改** UI 事件渲染逻辑（只要 Parser 输出统一 AgentEvent）。

---

## 9. 迁移阶段

| 阶段 | 内容 | 状态 |
|------|------|------|
| **P0** | `adapter/` + `adapters/opencode/` + `ChatService` 接管 stream | ✅ 完成 |
| **P1** | `store/`、`hub/api/server` 迁入；`base/` 仅保留领域逻辑 | ✅ 完成 |
| **P2** | 删除 OpenClaw 遗留（config/session/backends）；统一 session 路径 | ✅ 完成 |
| **P3** | `adapters/claude` stub + registry 多后端 UI | 待做 |
| **P4** | team-ok 改调 hub API；去掉 Telegram 硬依赖 | 待做 |

---

## 10. 设计约束

1. **Parser 是唯一允许 CLI 格式耦合的地方**
2. **Service 层不出现 `opencode`、`subprocess` 字样**
3. **UI 不出现 `part.text`、`sessionID` 等 CLI 字段**
4. **Session 键**：`{adapter_id}:{agent_id}:{workspace}`，与 CLI 无关
5. **规则文件**：agents/rules 生成 temp 文件，由 RunRequest 传入 Adapter

---

## 11. 编排内核（Orchestration Kernel）

> 业务编排层（项目 → 任务 DAG 执行），与上面的 chat/adapter 层正交。
> 详细决策见 `docs/framework-decisions.md`（D1–D18）。

旧 `skill/team/{task-executor,continuous-executor}` 双引擎已删除，统一为单一声明式状态机：

```
run_kernel.py (CLI 入口)
  → Process (单内核状态机：DAG 调度 / 失败语义 / 重试 / triage)
      → AgentPort (交互生命周期 / watchdog / 幂等 / token 计量)
          → Transport = AdapterTransport (opencode CLI 子进程)
      → Gate (契约 + 格式 + 完整性 确定性校验)
      → Registry (task_type 约束唯一来源 ← templates.yaml)
  → Store (SQLite 运行态真相库)
  → Observability API (hub/api/obs：项目总览 / 时间线 / 成本，只读 + SSE)
```

| 组件 | 文件 | 职责 |
|------|------|------|
| 入口 | `skill/team/common/run_kernel.py` | 装配 Store/AgentPort/Process，按 goal 跑项目 |
| 状态机 | `common/process.py` | DAG 调度、失败/重试、triage 委派 |
| 交互端口 | `common/agent_port.py` | InteractionRequest 投递、liveness、幂等、token 计量 |
| 传输 | `common/opencode_transport.py` | 构造 worker prompt → opencode 子进程 → AgentEvent |
| 门禁 | `common/gate.py` | 契约/格式/完整性校验（复用 `quality_gate` 证据校验工具） |
| 注册表 | `common/registry.py` | task_type 约束（读 `templates/templates.yaml`） |
| 真相库 | `common/store.py` | SQLite 运行态：interactions / events / tasks / tokens |
| 可观测 | `backend/hub/api/observability_api.py` | 只读查询 + run_event SSE |

## 12. config / path 出处

| 层 | 模块 | 根 / 真相 |
|----|------|----------|
| 服务端（Hub/UI） | `backend/hub/paths.py` | `MYTEAM_ROOT`（= 仓库根） |
| Worker / 编排 | `skill/team/common/paths.py` | `MYTEAM_ROOT`（env 可覆盖） |
| 系统配置真相 | `backend/store/system_config.py` | `config/system_config.json` |

`backend/base/system_config.py` 已降级为兼容垫片，仅 re-export `store.system_config`。
两个 `paths.py` 服务于两个不同 sys.path 包（server 在 `backend/`，worker 在 `skill/team/`），
均以 `MYTEAM_ROOT` 为根、`config/` 为配置目录，无定义漂移。

---

*文档版本：2026-06-02 · 新增 §11 编排内核 / §12 config·path 出处（D1–D18 切换收尾）*
