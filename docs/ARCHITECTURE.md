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
│  Orchestration            backend/common/ (单一 Process 内核)  │
│  run_kernel → Process/AgentPort/Gate/Store(SQLite)；直驱 CLI   │
│  业务定义/运行态在 business/（templates/workspaces/tasks/config）│
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

> 注：编排层已从旧 `executor`/`continuous-executor` 双引擎及 agent 驱动的老编排 skill
> 全面退役，统一为 `backend/common/` 的单一 **Process 内核**（见 §11），入口统一为 `run_kernel.py`。

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
> 详细决策见 `docs/framework-decisions.md`（D1–D19）。

旧 OpenClaw 时代的 agent 驱动编排 skill（`task-executor`/`continuous-executor`/`task-dispatch`/`task-queue`/`task-monitor`/`task-resume`/`project-init`/`agent-notify` 等）已整体退役，统一为单一声明式状态机；内核与系统工具已上移到 `backend/common/`：

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
| 入口 | `backend/common/run_kernel.py` | 装配 Store/AgentPort/Process，按 goal 跑项目 |
| 状态机 | `backend/common/process.py` | DAG 调度、失败/重试、triage 委派 |
| 交互端口 | `backend/common/agent_port.py` | InteractionRequest 投递、liveness、幂等、token 计量 |
| 传输 | `backend/common/opencode_transport.py` | 构造 worker prompt → opencode 子进程 → AgentEvent |
| 门禁 | `backend/common/gate.py` | 契约/格式/完整性校验（复用 `quality_gate` 证据校验工具） |
| 注册表 | `backend/common/registry.py` | task_type 约束（读 `business/templates/templates.yaml`） |
| 真相库 | `backend/common/store.py` | SQLite 运行态：interactions / events / tasks / tokens（`business/tasks/state.db`） |
| 可观测 | `backend/hub/api/observability_api.py` | 只读查询 + run_event SSE |

## 12. System / Strategy / Skill 三层边界

团队协作框架不是一个「大 Skill」，也不应把全部业务方法论硬编码进系统。当前定型为三层：

| 层 | 存放位置 | 职责 | 不应承担 |
|----|----------|------|----------|
| System Kernel | `backend/common/`、`backend/adapter/`、`backend/hub/api/observability_api.py` | Interaction 契约、Process、AgentPort、Gate、Store、Observability、预算/审计/恢复 | 具体行业执行方法、平台发布步骤、角色写作风格 |
| Strategy Registry | `business/templates/templates.yaml`、`business/config/agents_registry.json`、`business/rules/` | task_type、角色名册、验收标准、证据规则、团队默认策略 | 子进程调度、状态恢复、看门狗、运行态持久化 |
| Skill Pack | `business/skills/*/SKILL.md`、agent workspace 内 `AGENTS.md`/身份文件 | 教 agent 如何完成某类具体工作、调用外部工具、生成证据 | 改写系统状态、决定调度顺序、替代 Gate 或 Store |

判定规则：

1. 必须被测试、恢复、审计、重试、持久化的能力进 System Kernel。
2. 改变任务类型、角色选择、验收标准、流程策略的内容进 Strategy Registry。
3. 教某个 agent 如何完成具体工作的内容做 Skill。
4. 失败会导致系统状态不一致的能力不能放 Skill。
5. 失败只会影响某个任务质量的能力可以放 Skill。

### 当前归属审计

| 当前对象 | 归属 | 结论 |
|----------|------|------|
| `backend/common/process.py` | System Kernel | 正确：DAG 调度、one_shot/recurring、失败语义、预算暂停必须由系统保证 |
| `backend/common/agent_port.py` | System Kernel | 正确：心跳、watchdog、幂等、合法响应读取不可交给 Skill |
| `backend/common/contracts.py` | System Kernel | 正确：Interaction 结构是稳定边界，必须可测试和版本化 |
| `backend/common/registry.py` | System Kernel 读取入口 | 正确：代码只负责把策略注册表计算化；数据仍在 `business/templates/templates.yaml` |
| `business/templates/templates.yaml` | Strategy Registry | 正确：task_type、sections、check_rules、outcome_kind、acceptance_criteria 属业务策略 |
| `business/config/agents_registry.json` | Strategy Registry | 正确：Main 做 team_config 时读取的可用角色名册 |
| `business/rules/*.md` | Strategy Registry / Agent Rules | 正确：属于团队通用工作约束，不承担运行时机制 |
| `business/skills/publish-post/SKILL.md` | Skill Pack | 正确：只描述发布动作、脚本调用和证据要求，不调度、不持久化 |
| `config/system_config.json`、`config/skill_config.json` | System Config | 正确：端口、backend、通知开关等系统配置，不是业务技能 |

### Strategy Registry 结构与加载路径

当前策略注册表以 `business/templates/templates.yaml` 为核心，由 `backend/common/registry.py` 统一读取：

```
business/templates/templates.yaml
  task_type:
    outcome_kind: artifact | action
    deliverable_template:
      required_heading_level: 2
      sections:
        - name / description / required / example
    check_rules:
      required_sections: [...]
      file_exists: [...]
      evidence_url: {...}
      stub_floor: N
      must_include: [...]
    acceptance_criteria: [...]
```

加载链路：

```
Process → registry.get_spec(task_type)
        → business/templates/templates.yaml
        → 下发 constraints 给 Agent
        → Gate 用同一份 spec 校验 outcome
```

约束：

- `templates.yaml` 是 task_type 格式/验收策略的单一出处。
- `backend/common/registry.py` 只做解析、默认值派生和类型化访问，不承载业务文案。
- 新 task_type 必须先进入注册表，再按需补对应 Skill；不能只写 Skill 就让 Process 识别新任务。
- review checklist、quality floor、证据规则优先进入注册表或系统配置；只有“怎么执行某个检查”的操作步骤才进入 Skill。

## 13. config / path 出处

| 层 | 模块 | 根 / 真相 |
|----|------|----------|
| 服务端（Hub/UI） | `backend/hub/paths.py` | `MYTEAM_ROOT`（= 仓库根） |
| Worker / 编排 | `backend/common/paths.py` | `MYTEAM_ROOT`（env 可覆盖） |
| 系统配置真相 | `backend/store/system_config.py` | `config/system_config.json` |
| 业务配置 / 运行态 | 两个 `paths.py` 的 `BUSINESS_CONFIG_DIR` / `WORKSPACES_DIR` / `TASKS_DIR` | `business/`（gitignore） |

`backend/base/system_config.py` 已降级为兼容垫片，仅 re-export `store.system_config`。
两个 `paths.py` 同处 `backend/` 包树（server=`backend/hub`，内核=`backend/common`），
均以 `MYTEAM_ROOT` 为根：系统配置在 `config/`、业务配置与运行态在 `business/`，无定义漂移。

---

*文档版本：2026-06-04 · 增补 System / Strategy / Skill 三层边界、当前归属审计与策略注册表加载链路（§12）*
