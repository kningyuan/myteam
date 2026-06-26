# myteam Code Wiki

> 结构化代码文档：整体架构、模块职责、关键类与函数、依赖关系、运行方式。
> 与仓库源码同步（2026-06-26）。若与代码不符，以 `backend/`、`frontend/src/`、`business/templates/` 为准。

---

## 目录

1. [项目概览](#1-项目概览)
2. [整体架构](#2-整体架构)
3. [仓库目录结构](#3-仓库目录结构)
4. [后端架构详解](#4-后端架构详解)
5. [编排内核深入](#5-编排内核深入)
6. [CLI 适配器机制](#6-cli-适配器机制)
7. [前端架构（frontend）](#7-前端架构frontend)
8. [Business 策略层](#8-business-策略层)
9. [关键数据契约](#9-关键数据契约)
10. [关键类与函数索引](#10-关键类与函数索引)
11. [依赖关系](#11-依赖关系)
12. [配置与数据落盘](#12-配置与数据落盘)
13. [项目运行方式](#13-项目运行方式)
14. [不变量与设计决策](#14-不变量与设计决策)
15. [易混淆项速查](#15-易混淆项速查)

---

## 1. 项目概览

**myteam** 是一个轻量级 **多 Agent 协作平台**，由两部分组成：

- **Web Hub**：私聊 / 群聊 / Agent 管理 / Skill / MCP / Workflow / 项目可观测的 Web 控制台。
- **声明式编排内核**：把一个 `goal` 拆解成任务 DAG，按 wave 调度多 Agent，经确定性 Gate 校验、重试、triage，最终产出交付物。

Agent 的实际执行通过 **CLI 适配器**驱动（生产默认 **OpenCode**；另有 **Claude CLI** 适配器与 **stub** 测试后端）。myteam 本身不持有任何模型 token，所有模型调用都由外部 CLI 子进程完成。

### 1.1 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.12+、FastAPI、uvicorn、Pydantic、PyYAML、SQLite（WAL） |
| 前端 | React 19 + Vite 8 + TypeScript + Tailwind 4 + React Router 7 + Radix UI |
| CLI 后端 | OpenCode CLI / Claude CLI（外部依赖，subprocess 调用） |
| 存储 | SQLite（运行态真相）+ JSON（静态配置）+ 文件系统（交付物 / workspace） |
| 测试 | pytest（`PYTHONPATH=backend`） |

### 1.2 核心定位

> 让 AI Agent 的产出从「碰运气」变成「按流程交付」——Workflow 驱动、质量门禁保障、经验自动积累。

---

## 2. 整体架构

### 2.1 两条正交流

myteam 的关键设计是 **两条互不依赖的执行流**，共用 Agent 名册、Skill/MCP 挂载、workspace 与 SQLite 真相库。

```
A) Hub 交互流（人 ↔ Agent / 群），流式：
   浏览器 frontend (/v2)
     → FastAPI backend/hub/api/server.py
     → hub/services/chat_service（或 groups / notify）
     → base/agent_chat + adapter/registry
     → adapters/opencode | adapters/claude（子进程 CLI）
     → 统一 AgentEvent → SSE 推前端

B) 编排内核流（目标 → 多 Agent 自动交付），批处理：
   run_kernel.py 或 Hub「运行项目」
     → common/process.py（状态机）
     → common/agent_port.py（Interaction 投递 + submit_result 收卷）
     → common/gate.py（确定性验收）
     → SQLite business/tasks/state.db（真相）
     → 交付物 business/tasks/project/<id>/deliverables/
```

**编排内核不依赖 Hub 进程**——Hub 只是只读同一 SQLite 做可观测。两者可同时运行（都读 `business/tasks/state.db`）。

### 2.2 三层职责（System / Strategy / Skill）

| 层 | 路径 | 职责 | 决策规则 |
|----|------|------|----------|
| **System Kernel** | [backend/common/](../backend/common/)、[backend/adapter/](../backend/adapter/)、[backend/hub/](../backend/hub/) | Process、AgentPort、Gate、Store、contracts、Hub API、CLI 适配 | 失败会污染系统状态 → Kernel |
| **Strategy Registry** | [business/templates/](../business/templates/)、`business/config/agents_registry.json`、[business/workflows/](../business/workflows/)、[business/rules/](../business/rules/) | task_type、prompt 壳、workflow、名册、验收规则 | 改 task_type / 角色 / 验收 → Registry |
| **Skill / MCP Pack** | [business/skills/](../business/skills/)、`business/config/mcp_registry.json` | 具体执行方法论；MCP 工具目录 | 只影响单次任务质量 → Skill |

**重要**：新增 task_type 必须先改 [templates.yaml](../business/templates/templates.yaml)；只写 Skill 无法让 Process 识别任务。

### 2.3 关键路径常量

| 变量 | 作用 |
|------|------|
| `MYTEAM_ROOT` | 仓库根目录（`run.sh` 自动设为当前目录） |
| `PYTHONPATH` | 须包含 `backend/`（`run.sh` 自动设置） |
| `LOCAL_AGENT_PORT` | Hub 端口，默认 `8765` |
| `OPENCODE_CLI_PATH` | 覆盖 OpenCode 可执行文件路径 |
| `MYTEAM_V1_UI=1` | 临时开放经典 UI `frontend/`（默认关闭） |

路径常量定义：Hub 侧 [backend/hub/paths.py](../backend/hub/paths.py)；内核侧 [backend/common/paths.py](../backend/common/paths.py)（二者均相对 `MYTEAM_ROOT`）。

---

## 3. 仓库目录结构

```
myteam/
├── README.md                 # 项目主文档（结构最全）
├── AGENTS.md / CLAUDE.md     # AI 协作工作区说明
├── requirements.txt          # Python 依赖
├── run.sh                    # Hub start/stop；设 MYTEAM_ROOT、PYTHONPATH
├── comet.yaml / .cursorrules # 编辑器/工具规则
│
├── config/                   # 系统配置（*.json 通常 gitignore，运行时生成）
│   ├── system_config.json    #   端口、backend、模型、cli_path
│   └── skill_config.json     #   系统级 Skill/协作开关
│
├── backend/                  # 全部 Python 后端（见 §4）
│   ├── hub/                  #   FastAPI Hub（api + services）
│   ├── base/                 #   Agent 身份、工厂、群管理
│   ├── adapter/              #   CLI 抽象（protocol/events/registry/sse）
│   ├── adapters/             #   opencode / claude / stub_cli 实现
│   ├── store/                #   system_config / skill_config / sessions JSON 读写
│   ├── common/               #   编排内核 + 共享域 + tests/
│   ├── execution_harness/    #   execute 前后处理钩子（self-improve / review / distill）
│   └── memstack/             #   记忆栈（l1 / kb / preferences / orchestration）
│
├── frontend/              # 生产 Web UI（React SPA，见 §7）
├── frontend/                 # 经典 v1 UI（静态文件，默认关闭）
│
├── business/                 # 业务领域（配置与运行态混合，见 §8）
│   ├── templates/            #   Strategy 模板（入库）：templates.yaml 等
│   ├── rules/                #   Agent rules 合并源（入库）
│   ├── skills/               #   Skill 能力包（入库，每目录一个 SKILL.md）
│   ├── workflows/            #   声明式 Workflow YAML（入库）
│   ├── delivery_templates/   #   交付物 Markdown/HTML 模板
│   ├── hooks/                #   业务 Python hook
│   ├── config/               #   [gitignore] agents_registry、mcp_registry、groups…
│   ├── workspaces/           #   [gitignore] workspace-{agent_id}/
│   └── tasks/                #   [gitignore] state.db + project/{id}/
│
├── scripts/                  # 运维与回归脚本
└── docs/                     # 设计/决策/升级文档
```

---

## 4. 后端架构详解

单棵 Python 树 `backend/`，设置 `PYTHONPATH=backend` 后按包导入。

### 4.1 分层总览

| 包 | 职责 |
|----|------|
| [hub/api/](../backend/hub/api/) | FastAPI 薄路由（`server.py` 入口 + `routes/*` + `skills_api` + `mcp_api` + `observability_api`） |
| [hub/services/](../backend/hub/services/) | 聊天、群组、项目启动、SSE、Agent 注册表业务 |
| [base/](../backend/base/) | Agent 工厂、身份组装、群管理、agents_config 读写 |
| [adapter/](../backend/adapter/) | `CLIAdapter` 抽象、`AgentEvent`、SSE 编码、registry |
| [adapters/](../backend/adapters/) | opencode / claude / stub_cli 具体实现 |
| [store/](../backend/store/) | 系统级 JSON 配置（system_config、skill_config、sessions） |
| [common/](../backend/common/) | 编排内核 + 共享领域（Process、AgentPort、Gate、Store SQLite、Skill/MCP catalog） |

### 4.2 Hub API 路由聚合

| 模块 | 前缀 / 路径 | 职责 |
|------|-------------|------|
| [routes/chat.py](../backend/hub/api/routes/chat.py) | `/api/chat` | DM SSE、cancel、status |
| [routes/groups.py](../backend/hub/api/routes/groups.py) | `/api/groups` | 群 CRUD、消息、@mention |
| [routes/agents.py](../backend/hub/api/routes/agents.py) | `/api/agents` | 名册、backend/model、Skill/MCP 挂载 |
| [routes/projects.py](../backend/hub/api/routes/projects.py) | `/api/projects` | 创建/运行/取消项目、交付物 |
| [routes/workflows.py](../backend/hub/api/routes/workflows.py) | `/api/workflows` | Workflow YAML CRUD、校验 |
| [routes/config.py](../backend/hub/api/routes/config.py) | `/api/...` | sync-skills、sync-mcp、task-types 等 |
| [skills_api.py](../backend/hub/api/skills_api.py) | `/api/skills` | Skill 库 CRUD、章节、文件 |
| [mcp_api.py](../backend/hub/api/mcp_api.py) | `/api/mcp` | MCP 库 CRUD、enabled |
| [observability_api.py](../backend/hub/api/observability_api.py) | `/api/obs` | 项目/Agent 可观测、run_event SSE |

静态资源：`/` → 重定向 `/v2/`；`frontend/dist` 作为 SPA；`frontend/` 仅 `MYTEAM_V1_UI=1` 时可访问 `/classic`。

### 4.3 Hub 入口 lifespan（[server.py](../backend/hub/api/server.py)）

`lifespan()` 启动时执行：
1. `ensure_agents_config_entries` 补全 agent 配置；
2. `sync_all_agent_skill_mounts` / `sync_all_agent_mcp_mounts` 同步 Skill/MCP 挂载到各 workspace；
3. `_auto_resume_on_startup` 后台线程：`reconcile_on_start` 对账 GC → `gc_workspace` → 自动续跑所有 `in_progress`/`paused` 项目。

### 4.4 hub/services 关键服务

| 文件 | 作用 |
|------|------|
| [chat_service.py](../backend/hub/services/chat_service.py) | DM 流式聊天（`stream(use_memory=True)`） |
| [group_broadcast.py](../backend/hub/services/group_broadcast.py) | 群聊多 Agent 串行/讨论 loop |
| [project_launch.py](../backend/hub/services/project_launch.py) | `run_kernel_bg` / `resume_kernel_bg` 后台启动内核 |
| [kernel_run.py](../backend/hub/services/kernel_run.py) | Hub 调内核的桥接 |
| [stream_fanout.py](../backend/hub/services/stream_fanout.py) | SSE 流扇出 |
| [sse_bridge.py](../backend/hub/services/sse_bridge.py) | 事件桥接 |
| [agent_registry.py](../backend/hub/services/agent_registry.py) | Agent 注册表业务 |

### 4.5 base/ 层

| 文件 | 作用 |
|------|------|
| [agent_chat.py](../backend/base/agent_chat.py) | Agent 后端配置（`BackendConfig`、`get_agent_backend_config`）、scan/delete |
| [agent_factory.py](../backend/base/agent_factory.py) | `generate_agent` / `suggest_agent_id` |
| [agent_identity.py](../backend/base/agent_identity.py) | `AgentIdentityBuilder`、`multi_agent_manager`（组装 AGENTS.md/IDENTITY.md/SOUL.md） |
| [group_manager.py](../backend/base/group_manager.py) | 群组管理 |
| [system_config.py](../backend/base/system_config.py) | **deprecated shim**，re-export `store.system_config` |

### 4.6 store/ 层（注意：是 JSON 配置，不是 SQLite）

| 文件 | 作用 |
|------|------|
| [system_config.py](../backend/store/system_config.py) | 端口、默认 backend/model、`backends.opencode.cli_path`、模型列表（首次自动生成） |
| [skill_config.py](../backend/store/skill_config.py) | 系统级 Skill/协作开关 |
| [sessions.py](../backend/store/sessions.py) | CLI session 映射 |

### 4.7 execution_harness/ 与 memstack/

- [execution_harness/](../backend/execution_harness/)：execute 前后处理钩子，分 `pre/`（engineer_loop、prepare、self_improve、lesson_inject）、`post/`（review、self_eval、rubric_eval、distill、promote、failure_patterns、lesson）、`skill/`（references、umbrella）、`identity/`、`injection/`。入口 [facade.py](../backend/execution_harness/facade.py)（`inject_for_execute` / `prepare_execute_harness`）。
- [memstack/](../backend/memstack/)：记忆栈，分层 `l1/`（短期会话记忆，mem0/native/sqlite/noop）、`kb/`（知识库）、`preferences/`（偏好库）、`orchestration/`（experience/anysearch）。统一门面 [facade.py](../backend/memstack/facade.py)。

---

## 5. 编排内核深入

内核代码集中在 [backend/common/](../backend/common/)，是 myteam 的核心。入口 [run_kernel.py](../backend/common/run_kernel.py)。

### 5.1 内核组装流程（[run_kernel.py](../backend/common/run_kernel.py) `run_project()`）

```
run_project(project_id, goal, ...)
  ├─ backend = _system_default_backend()        # 读 system_config，默认 opencode
  ├─ store = Store()                             # SQLite 真相库
  ├─ reconcile_on_start(store)                   # 启动对账 GC（D8）：清理上次残留 pending/running
  ├─ gc_workspace(store)                         # 清 workspace 临时件
  ├─ transport = AdapterTransport(backend, ...)  # 真实 CLI 传输层
  ├─ 若 workflow：ensure_workflow_ready → roster + tasks + loops
  ├─ kernel_configs_for_run(...) → base_cfg + watchdog
  ├─ port = AgentPort(transport, store, watchdog, budget_checker)
  ├─ proc = Process(store, port, base_cfg, hooks=kernel_project_hooks())
  └─ proc.run(project_id, goal=goal, agents=..., tasks=..., workflow=..., loops=...)
```

`run_kernel.py` CLI 参数：`--goal`、`--mode one_shot|recurring`、`--budget`、`--max-cycles`、`--review`、`--split`、`--backend opencode|claude`、`--workflow <ID>`、`--resume`、`--demo`、`--init`。

### 5.2 Process 状态机（[process.py](../backend/common/process.py)）

`Process` 是声明式「Step + Gate」单内核（D10/D18），合并了旧的 task-executor 与 continuous-executor。串行驱动 DAG（D12），每步经 AgentPort 投递统一 Interaction（D11），Gate 判格式/完整性，质量交 Agent 自评 + 评审。

**项目状态机**：
```
team_config → task_plan → wave 调度（DAG）
  → 每个 task：plan? → execute → Gate → (review?) → finalize
  → 失败：可重试 → 自动重试有限次 → 耗尽 failed → 委托 Main kind=triage
项目级：全 completed → completed；有不可恢复 failed → partially_failed / failed
```

`Process` 内部组合三个组件：
- `_pipeline: TaskPipeline` — 单任务执行管线（plan/execute/gate/finalize）；
- `_decisions: DecisionPipeline` — team_config / task_plan / triage 决策；
- `_expander: PlanExpander` — evaluate 拆分（`split_enabled`）。

**关键方法**：
- `Process.run(project_id, *, title, goal, agents, tasks, workflow, loops) -> ProjectOutcome`
- `Process.resume(project_id)` — 断点续跑

### 5.3 AgentPort（[agent_port.py](../backend/common/agent_port.py)）

把一次 Interaction 投递给 Agent 并取回合法结果（D12/D7/D8）。

- **同步阻塞** `run(InteractionRequest) -> AgentPortResult`，串行（同一时刻一个 interaction）。
- **混合取回**：事件流负责「存活 + 计量」；最终结果由 Agent 侧 `submit_result` 校验后原子写 `.response`。
- **两段式看门狗**（D7）：首个事件=已送达+存活；`soft_idle` 疑似卡死（标记+告警）；`hard_idle` 取消+重试。
- **幂等治理**（D8）：按 `interaction_id` 命名；响应须 interaction_id 匹配且 mtime 晚于请求；派发前清旧文件。

**关键类型**：
```python
@dataclass
class WatchdogConfig:
    soft_idle_sec: float = 120.0    # 无事件超此 = 疑似卡死
    hard_idle_sec: float = 300.0    # 无事件超此 = 取消 + 重试
    max_attempts: int = 3
    def idle_limits(kind) -> tuple[soft, hard]

@dataclass
class AgentPortResult:
    status: str               # done | timed_out | no_response | error
    response: Optional[dict]
    interaction_id: str
    attempt: int

class AgentPort:
    def __init__(transport, store, config, budget_checker, token_sink)
    def run(request: InteractionRequest) -> AgentPortResult
```

`Transport = Callable[[DeliveryContext], None]` 可注入，便于测试与多后端。

### 5.4 Gate 确定性门禁（[gate.py](../backend/common/gate.py)）

原则（D14/D15）：**框架只判契约 + 格式 + 完整性（客观/确定性/可复现/阻塞）；质量（好坏）归 Agent**（自评 + 评审）。

三类门禁：
1. **契约门禁** `check_contract(response)` — 响应符合 Interaction 契约（`contracts.validate_response_dict`）。
2. **格式/完整性门禁** — 对照格式注册表（[registry.py](../backend/common/registry.py) `FormatSpec`）：必需章节 / 标题层级 / `file_exists` / 防 stub；action 型校验证据（URL 形态 + 截图存在）。
3. **质量** — 不在 Gate，由 Agent 自评（D11）+ cross_review。

```python
@dataclass
class GateResult:
    passed: bool
    failures: list[dict]
    skipped: bool = False
    feedback: str = ""

def check_contract(response: dict) -> GateResult
# 另有 check_format / check_evidence / check_code_project 等
```

### 5.5 格式注册表（[registry.py](../backend/common/registry.py)）

task_type 约束的**单一出处**。Process 下发约束、Gate 据此校验，源出同一（D10-D/D14/D15）。

```python
@dataclass
class FormatSpec:
    task_type: str
    display_name: str
    outcome_kind: str = "artifact"      # artifact | action（D15）
    required_sections: list[str]        # 格式/完整性
    required_heading_level: int = 2
    sections: list[dict]
    file_exists: list[str]             # 必须存在的引用文件
    evidence: dict                     # action 证据规则
    stub_floor: int                    # 防 stub 下限（D14）
    must_include: list[str]            # 默认不强制
    acceptance_criteria: list[str]     # 自评 + 评审共用
    delivery_profile: str
    template_id: str

def get_spec(task_type: str) -> FormatSpec   # 框架下发与 Gate 校验共用
def load_registry() -> dict
def is_stub(text: str) -> bool
```

数据存 [templates.yaml](../business/templates/templates.yaml)，本模块是其计算化单一读取入口。

### 5.6 Store SQLite 真相库（[store.py](../backend/common/store.py)）

运行态状态 = SQLite（零新依赖、单 `.db` 文件、ACID）。表：`project` / `task` / `interaction` / `run_event` / `memory`。

- 人类产物仍是文件（`deliverables/*.md`、`evidence/`）。
- 静态配置仍是 JSON。
- 并发：WAL + busy_timeout；每线程独立连接。

**状态机**（D18）：
```
interaction: pending → running → done | failed | cancelled | timed_out
task:        pending → in_progress → completed | needs_review | failed | blocked
```

后端实现可换：[store_backend.py](../backend/common/store_backend.py)（抽象）+ [store_sqlite.py](../backend/common/store_sqlite.py)（SQLite 实现）。

### 5.7 submit_result 交卷通道（[submit_result.py](../backend/common/submit_result.py)）

Agent 侧回传工具（D11/D12）。职责：完成 Interaction 后，按契约**本地校验**结果，通过才**原子写**入 `.response`；校验失败直接报错（**拒绝，而非抢救**——D1/F1，无 JSON 修复路径）。

**编排派发门**：仅当 AgentPort 注入 `MYTEAM_DISPATCH_TOKEN`（=interaction_id）且存在匹配 `.request` 时才允许写入；私聊/群聊交互任务不得调用。

```python
def submit(response: dict, response_path, *, require_dispatch=True) -> Path
class SubmitError(ValueError)   # 契约校验失败
```

### 5.8 内核其它关键模块

**Agent / Skill / MCP**

| 文件 | 作用 |
|------|------|
| [agent_registry.py](../backend/common/agent_registry.py) | 读 `agents_registry.json` |
| [agent_skills.py](../backend/common/agent_skills.py) | Skill 挂载解析、`build_skill_context`、strip AGENTS.md Skill 节 |
| [agent_mcp.py](../backend/common/agent_mcp.py) | MCP 挂载解析、`build_mcp_context` |
| [skill_catalog.py](../backend/common/skill_catalog.py) | 扫描 `business/skills/*/SKILL.md` |
| [mcp_catalog.py](../backend/common/mcp_catalog.py) | 读写 `business/config/mcp_registry.json` |
| [agent_transport.py](../backend/common/agent_transport.py) | 构建 team_config/task_plan/execute worker prompt；`AdapterTransport` |
| [agent_model.py](../backend/common/agent_model.py) | agents_config 与 registry 对齐（`resolve_agent_backend/model`） |
| [agent_execution.py](../backend/common/agent_execution.py) | Agent 执行锁（chat vs kernel 互斥） |
| [agent_bootstrap.py](../backend/common/agent_bootstrap.py) | 创建 Agent workspace（`auto_create_agent`） |

**Workflow / task_type / 交付**

| 文件 | 作用 |
|------|------|
| [workflow_loader.py](../backend/common/workflow_loader.py) / [workflow_validate.py](../backend/common/workflow_validate.py) | 加载校验 `business/workflows/*.yaml` |
| [workflow_bootstrap.py](../backend/common/workflow_bootstrap.py) | `ensure_workflow_ready` |
| [delivery_templates.py](../backend/common/delivery_templates.py) / [delivery_template_store.py](../backend/common/delivery_template_store.py) | 交付模板 |
| [delivery_profiles.py](../backend/common/delivery_profiles.py) | 交付形态 profile |
| [deliverable_guarantee.py](../backend/common/deliverable_guarantee.py) | 骨架保证（`scaffold_markdown_deliverable`） |
| [prompt_composer.py](../backend/common/prompt_composer.py) / [prompt_injections.py](../backend/common/prompt_injections.py) / [prompt_templates.py](../backend/common/prompt_templates.py) | Execute 等 prompt 壳 |
| [rules_merge.py](../backend/common/rules_merge.py) | 合并 universal/worker/AGENTS rules 文件 |

**项目运行时 / 可观测 / Loop**

| 文件 | 作用 |
|------|------|
| [project_runtime.py](../backend/common/project_runtime.py) / [project_admin.py](../backend/common/project_admin.py) / [project_cancel.py](../backend/common/project_cancel.py) | 项目生命周期 |
| [project_artifacts.py](../backend/common/project_artifacts.py) / [project_hooks.py](../backend/common/project_hooks.py) / [kernel_project_hooks.py](../backend/common/kernel_project_hooks.py) | 产物与 hook |
| [observability.py](../backend/common/observability.py) / [token_usage.py](../backend/common/token_usage.py) / [audit_log.py](../backend/common/audit_log.py) | 指标、token、审计 |
| [loop_runtime.py](../backend/common/loop_runtime.py) | Workflow 内 loop 步骤（`run_loop`、`LoopSpec`、`RunLoopDeps`） |
| [loop_discussion_runtime.py](../backend/common/loop_discussion_runtime.py) / [roundtable_runtime.py](../backend/common/roundtable_runtime.py) | 讨论型 loop / 圆桌编排 |
| [dag_dispatch.py](../backend/common/dag_dispatch.py) | DAG 辅助（`deps_block`、`ready_tasks`、`derive_project_status`） |
| [plan_expansion.py](../backend/common/plan_expansion.py) / [plan_gate.py](../backend/common/plan_gate.py) | 规划展开与闸门 |
| [decision_pipeline.py](../backend/common/decision_pipeline.py) | team_config/task_plan/triage 决策管线 |
| [task_pipeline.py](../backend/common/task_pipeline.py) | 单任务执行管线 |
| [workspace_gc.py](../backend/common/workspace_gc.py) | workspace 清理 |
| [thinking_trace.py](../backend/common/thinking_trace.py) | 思考链持久化 |

---

## 6. CLI 适配器机制

**适配器隔离**是 myteam 的核心抽象（`docs/ARCHITECTURE.md` §10），是必须遵守的不变量。

### 6.1 跨 CLI 数据契约（仅两个）

| 契约 | 定义 | 含义 |
|------|------|------|
| `RunRequest` | [adapter/protocol.py](../backend/adapter/protocol.py) | 一次 Agent 运行请求（与 CLI 无关） |
| `AgentEvent` | [adapter/events.py](../backend/adapter/events.py) | 统一流式事件（UI 与 Service 层唯一事件契约） |

### 6.2 CLIAdapter 抽象（[adapter/protocol.py](../backend/adapter/protocol.py)）

```python
class CLIAdapter(ABC):
    @property
    def id(self) -> str: ...               # opencode | claude | stub_cli
    @property
    def display_name(self) -> str: ...
    @property
    def capabilities(self) -> AdapterCapabilities: ...   # streaming/tool_use/native_skill_registry...
    def list_models(self) -> list[ModelInfo]: ...
    def get_default_model(self) -> str: ...
    def run(self, request: RunRequest) -> Generator[AgentEvent, None, None]: ...
    def sync_agent_skills(agent_id, workspace, skill_ids) -> dict   # 默认 no-op
    def sync_agent_mcp(agent_id, workspace, server_ids) -> dict     # 默认 no-op
```

### 6.3 AgentEvent（[adapter/events.py](../backend/adapter/events.py)）

```python
class EventKind(str, Enum):
    STEP_START / TEXT / REASONING / TOOL_USE / TOOL_RESULT / STEP_FINISH / ERROR / SESSION

@dataclass
class AgentEvent:
    kind: EventKind
    data: dict
    def to_thinking_payload(self) -> dict | None   # 转 SSE thinking.data
```

### 6.4 适配器实现

| 文件 | 作用 |
|------|------|
| [adapters/opencode/adapter.py](../backend/adapters/opencode/adapter.py) | `OpenCodeAdapter`：`opencode run` 子进程、严格 Skill 环境变量 |
| [adapters/opencode/parser.py](../backend/adapters/opencode/parser.py) | OpenCode JSON 行 → AgentEvent（**唯一**知道 opencode 输出格式的地方） |
| [adapters/opencode/skill_sync.py](../backend/adapters/opencode/skill_sync.py) | workspace `.opencode/skills` 符号链接 |
| [adapters/opencode/mcp_sync.py](../backend/adapters/opencode/mcp_sync.py) | 写 `opencode.json` MCP 块 |
| [adapters/claude/adapter.py](../backend/adapters/claude/adapter.py) | Claude CLI 包装 |
| [adapters/claude/parser.py](../backend/adapters/claude/parser.py) | Claude 输出 → AgentEvent |
| [adapters/stub_cli.py](../backend/adapters/stub_cli.py) | 测试用假 CLI |
| [adapter/subprocess_cli.py](../backend/adapter/subprocess_cli.py) | 子进程通用基类 |
| [adapter/registry.py](../backend/adapter/registry.py) | `AdapterRegistry`（`register`/`get`/`list_models_all`），单例 `registry` |

### 6.5 隔离规则（不可违反）

- `adapters/<cli>/parser.py` 是**唯一**允许知道 CLI 原始输出格式的地方。
- 服务层（`hub/services/`、`base/`）**不得**包含 `opencode` 或 `subprocess`。
- UI **不得**引用 CLI 专属字段（`part.text`、`sessionID`、raw opencode JSON）——只消费 `thinking` SSE 事件的 `type`。
- **新增 CLI** = 新建 `adapters/<cli>/` 目录 + parser + 更新 `agent_transport._default_adapter()`，**无需改 UI**。
- 后端选择：`run_kernel.py --backend opencode|claude`；per-agent 在 `agents_config.json`。

---

## 7. 前端架构（frontend）

生产 UI：[frontend/](../frontend/)（React 19 + Vite 8 + TypeScript + Tailwind 4 + React Router 7）。构建产物 `frontend/dist/`（gitignore），Hub 在 `/v2` 提供 SPA。分层详见 [frontend/ARCHITECTURE.md](../frontend/ARCHITECTURE.md)。

经典 UI：`frontend/`（纯静态），默认不对外；`MYTEAM_V1_UI=1` 后访问 `/classic`。

### 7.1 技术栈

- React 19.2 + react-dom 19.2，TypeScript ~6.0，Vite 8
- 路由：`react-router-dom` ^7.17（`BrowserRouter basename="/v2"`）
- UI：Tailwind CSS v4 + Radix UI primitives（dialog/label/scroll-area/select/separator/slot/tabs）
- 工具：`class-variance-authority`、`clsx`、`tailwind-merge`、`lucide-react`、`sonner`
- 无后端框架依赖（纯 SPA，调 Hub REST `/api/*`）；无测试框架

### 7.2 分层（数据流自上而下，HTTP 永远在最底层）

```
App.tsx (BrowserRouter basename=/v2)
  → Pages（路由级壳：DashboardPage、ProjectsPage、GroupChatPage…）
  → Sections（页内大功能块：ChatSection、ProjectsSection…）
  → Components（按域分组：chat/、project/、workflow/、skills/、mcp/、manage/、ui/、layout/）
  → Hooks（useAgentChat、useResourceQuery — 编排 ports + 本地态）
  → Ports（ChatPort、ProjectsPort — TS 接口 + 默认 Hub 实现，可替换）
  → lib/api/*（按域拆分的薄 HTTP 客户端）
  → Hub REST /api/*
```

业务规则留在 Hub（Python），前端 API 层不做校验/编排。

### 7.3 路由（[App.tsx](../frontend/src/App.tsx)）

| 路径 | Section / Page |
|------|----------------|
| `/v2/` | Dashboard |
| `/v2/chat[/:agentId]` | 私聊 |
| `/v2/groups[/:groupId]` | 群聊 |
| `/v2/projects[/:projectId]` | 项目列表与详情 |
| `/v2/execute[/:projectId/:taskId]` | 单任务执行 |
| `/v2/manage[/:tab[/:itemId]]` | Agent / 后端 / 任务类型管理 |
| `/v2/workflows[/:workflowId]` | Workflow 编辑器 |
| `/v2/skills[/:skillId]` | Skill 库 |
| `/v2/mcp[/:serverId]` | MCP 库 |
| `/v2/settings[/:section]` | 系统设置 |

### 7.4 API 客户端（[src/lib/api/](../frontend/src/lib/api/)）

| 文件 | 职责 |
|------|------|
| [client.ts](../frontend/src/lib/api/client.ts) | `hubFetch`、`readStreamWithAbort`、`parseSseDataLines`、`parseSseLineBuffer`、`isAbortError` |
| [projects.ts](../frontend/src/lib/api/projects.ts) | 项目 + `/api/obs/projects`（`ProjectSummary`、`ProjectDetail`、`TaskDetail`） |
| [agents.ts](../frontend/src/lib/api/agents.ts) | Agent CRUD、sync skills/mcp |
| [chat.ts](../frontend/src/lib/api/chat.ts) | DM chat（`sendAgentChat`、`cancelAgentChat`） |
| [groups.ts](../frontend/src/lib/api/groups.ts) | 群组 |
| [workflows.ts](../frontend/src/lib/api/workflows.ts) | Workflow、task-types、delivery-templates |
| [config.ts](../frontend/src/lib/api/config.ts) | backends、obs summary |
| [index.ts](../frontend/src/lib/api/index.ts) | barrel 重导出 |

### 7.5 SSE 流式消费（两条链路）

**(A) Agent 对话流 — fetch + 手写 SSE 解析**
- [client.ts](../frontend/src/lib/api/client.ts) `readStreamWithAbort`：从 `ReadableStream` 取 reader，注册 `signal.abort` → `reader.cancel()`（关键：Abort 时必须 `reader.cancel()`，否则 SSE 读循环不结束）；`parseSseLineBuffer` 按 `\n` / `\n\n` 切帧，剥 `data: ` 前缀，遇 `[DONE]` 终止。
- [chat.ts](../frontend/src/lib/api/chat.ts) `sendAgentChat`：`fetch(/api/chat/<agentId>?message=...)` → `TextDecoder` 累积 → `parseSseLineBuffer` → `JSON.parse` → `onChunk(event)`。
- [agentChatStream.ts](../frontend/src/lib/agentChatStream.ts) — **全局对话流状态机**：切页/换 Agent 不中断底层 CLI，仅用户点「停止」才取消。模块级 `sessions: Map<agentId, AgentChatSession>`、`agentListeners`、`globalListeners`、`settleListeners`（订阅模式，跨路由存活）。事件类型：`thinking`（累积文本与思考链）、`citations`、`error`、`done`。后台 `EventSource` 订阅 `/api/agents/<id>/events`（断线 3s 重连）。

**(B) 项目进度 / 群事件流 — EventSource**
- `subscribeProjectStream`（`EventSource`）
- `subscribeGroupEvents`（`EventSource`）

### 7.6 Port 模式（[src/lib/ports/](../frontend/src/lib/ports/)）

Port 镜像后端 adapter 抽象：hooks/features 依赖接口而非 `fetch`，可替换为 mock / 离线 / 备用后端。

- [ChatPort.ts](../frontend/src/lib/ports/ChatPort.ts)：`interface ChatPort { listMessages; streamChat; cancelChat }`
- [ProjectsPort.ts](../frontend/src/lib/ports/ProjectsPort.ts)：`interface ProjectsPort { listProjects; getProject; runProject }`
- [hubChatPort.ts](../frontend/src/lib/ports/hubChatPort.ts) / [hubProjectsPort.ts](../frontend/src/lib/ports/hubProjectsPort.ts)：默认实现，委托 `@/lib/api/*`

**FE/BE 边界规则**：改动影响产品行为或校验 → 落 Hub，而非 `src/lib/api/*`。前端只显示 + 订阅 SSE。

**缓存失效**（[dataRefresh.ts](../frontend/src/lib/dataRefresh.ts)）：mutation 后调 `invalidateResources("projects"|"agents"|...)`，`useResourceQuery` 订阅者重载。

---

## 8. Business 策略层

### 8.1 task_type 定义源（[templates.yaml](../business/templates/templates.yaml)）

每个 task_type 通用字段：`display_name`、`recommended_skills[]`、`deliverable_template`（`required_heading_level` + `sections[]`：`name/description/required`）、`check_rules`（`required_sections[]` + `min_length`）；可选 `outcome_kind`。

代表性条目：

| task_type | display_name | outcome_kind | 关键 required_sections | min_length |
|---|---|---|---|---|
| `research` | 调研 | artifact | 调研目标 / 信息来源 / 关键发现 / 结论 | 200 |
| `coding` | 编码 | artifact | 需求分析 / 设计方案 / 代码实现 / 测试结果 | 200 |
| `review` | 评审 | artifact | 评审范围 / 问题列表 / 改进建议 | 200 |
| `competitive-analysis` | 竞品分析 | artifact | 竞品概览 / 能力对比矩阵 / 优劣势分析 / 差异化机会 | 300 |
| `product-planning` | 产品规划 | artifact | 产品定位 / 核心功能 / 优先级排序 / 实施路线图 | 300 |
| `product-research` | 产品调研 | artifact | 调研目标 / 市场概况 / 竞品分析 / 用户洞察 / 机会与建议 | 400 |
| `data-analysis` | 数据分析 | artifact | 分析问题与口径 / 数据来源与质量 / 分析过程与方法 / 关键发现 / 结论与行动建议 | — |
| `acceptance-report` | 验收报告 | artifact | 验收范围 / 验收结果 / 问题清单 / 结论与建议 | 300 |

### 8.2 Workflow YAML（[business/workflows/](../business/workflows/)）

**标准顶层键**：`id` / `name` / `version` / `description` / `tasks`。`loops` + `options` 是 v2 迭代 workflow 的可选键（见 `_examples/iteration-v2-fixture.yaml`）。**`roster` 不是 workflow 键**——团队花名册在 [business-roster.json](../business/templates/business-roster.json) 与 `business/config/agents_registry.json`，workflow 通过 task 的 `agent_id` 引用。

**标准 task 字段**（以 `simple-report.yaml` 为例）：`id`、`agent_id`、`task_type`、`template_id`（对应 [delivery_templates/](../business/delivery_templates/)）、`name`、`description`（固定四段：【范围】【输入】【交付】【质量】）、`dependencies`（task id 列表，构成 DAG）。

**示例**：
- `research-report.yaml`：`step-collect`(research) → `step-report`(product)
- `competitive-analysis.yaml`：`step-collect`(research) → `step-compare`(product) → `step-report`(product)

**v2 迭代 workflow**（`_examples/iteration-v2-fixture.yaml`）：`options`（开关）、`loops[]`（每项含 `id`、`max_rounds`、`min_rounds`、`bodies`、`assess`、`transition[]`：`when: deliverable_marker` + `marker: "ITERATION: PASS|STOP|CONTINUE"` → `action: exit|continue`）。

**hook profile**（[profiles/work-review-alignment.yaml](../business/workflows/profiles/work-review-alignment.yaml)）：不是任务图，而是 hook 配置（`hook_module`、`work_agent`/`review_agent`、`max_alignment_turns`、`pass_marker`/`fail_marker`），对应 [business/hooks/work_review_alignment.py](../business/hooks/work_review_alignment.py)。

### 8.3 Skills 目录（[business/skills/](../business/skills/)）

扁平目录（`<skill_id>/SKILL.md`），分类由元数据 YAML 维护，**不对应物理子目录**。

- [catalog.yaml](../business/skills/catalog.yaml)（version 0.2）— 全局 skill 路由表，每条字段：`id`、`task_types[]`（多对多）、`description`、`router`（指向 `SKILL.md`）；可选 `means_root` / `execution` / `probe` / `verify` / `means[]` / `deliverables[]`。约 30 项。
- [categories.yaml](../business/skills/categories.yaml)（version 1）— 纯展示分类（标签）：`methodology` / `code-project` / `officecli` / `workflow-creation`。

**关键设计声明**（catalog.yaml 顶部）：Agent 按 task_type 自选 skill，**workflow 不得写死 skill 路径**；`geo-*` / `data-analysis` 由内核 `templates.yaml` 直驱，无独立 Skill 目录。

### 8.4 Rules 层（[business/rules/](../business/rules/)）

5 个文件，按 `rules_profile` 选择性加载：

| 文件 | 加载场景 | 作用 |
|---|---|---|
| [universal-rules.md](../business/rules/universal-rules.md) | 全员默认 | 基本行为准则 + 规则加载说明 |
| [ethos.md](../business/rules/ethos.md) | 全员默认 | 团队哲学：Boil the Ocean / Search Before Building / User Sovereignty |
| [interactive-guide.md](../business/rules/interactive-guide.md) | `rules_profile=interactive`（私聊/群聊） | 允许 Read/Write/Bash/WebSearch；**禁止**碰 `.trigger`/`.response`、`submit_result`、`deliverables/` |
| [brainstorming-guide.md](../business/rules/brainstorming-guide.md) | `rules_profile=discussion`（圆桌讨论） | 仅允许只读 + 调研；**禁止** Write/Edit/Bash |
| [worker-template.md](../business/rules/worker-template.md) | `rules_profile=workflow_execute`（编排 execute） | Agent 只思考创作，流程由 executor 控制；读 `.trigger/` 返回 JSON 到 `.response/` |

`interactive` 与 `discussion` 不加载 `worker-template.md`/`AGENTS.md` 执行段；`workflow_execute` 不加载交互/讨论专规。`conversation` 是 `interactive` 的兼容别名。

### 8.5 Skill / MCP 配置链

```
UI 勾选 / MCP 页编辑
  → business/config/agents_registry.json（skills[]、mcp_servers[]）
  → business/config/mcp_registry.json（全局 MCP 目录 + enabled）
  → adapter.sync_agent_skills / sync_agent_mcp
  → workspace 内 .opencode/skills、opencode.json
  → 每轮 chat/execute：build_skill_context / build_mcp_context 注入摘要
```

边界摘要每轮注入；**完整 SKILL.md** 仅在 Agent 主动 Read 时进入上下文。MCP 工具 schema 由 CLI 进程加载，不写入 Hub prompt。**不再**向 AGENTS.md 自动写入 `## 已挂载 Skill/MCP`（历史段落会在保存/启动时被 strip）。

### 8.6 Workspace 交卷通道

每个 Agent 工作区（`business/workspaces/workspace-{agent_id}/`，gitignore 运行态）：

| 路径 | 作用 |
|------|------|
| `AGENTS.md` / `IDENTITY.md` / `SOUL.md` / `USER.md` | 人设与规则；execute 时 rules 会合并 AGENTS.md |
| `.trigger/{interaction_id}.request` | Interaction 请求快照（审计）；CLI 由内存 prompt 驱动 |
| `.response/{interaction_id}.response` | `submit_result` 原子写入的契约 JSON |
| `.opencode/skills/{id}/` | Hub 同步的 Skill 符号链接（OpenCode） |
| `opencode.json` | Hub 同步的 MCP 块（OpenCode） |

Agent **不互读** `.trigger`；协作靠 **DAG 依赖 + 交付物路径 + 上游 summary**。

---

## 9. 关键数据契约

### 9.1 Interaction 契约（[contracts.py](../backend/common/contracts.py)，D11/D5/D15）

框架 ↔ Agent 之间**只交换一对**结构：`InteractionRequest` / `InteractionResponse`，用 `kind` 做辨识联合。

**Request 信封**：
```python
class InteractionRequest(BaseModel):
    interaction_id: str
    schema_version: str = "1.0"
    kind: Kind                        # team_config|task_plan|plan|evaluate|execute|review|triage|skill_review
    project_id: str
    task_id: Optional[str]
    agent_id: str
    intent: str = ""
    input: dict = {}
    context: dict = {}
    response_schema: str = ""         # 注册表引用，如 "execute.result@1.0"
    constraints: dict = {}
    deadline_sec: Optional[int]
    retry_feedback: list[str] = []
```

**Response 辨识联合**（`Field(discriminator="kind")`）：

| kind | result 类型 | 关键字段 |
|------|-------------|----------|
| `team_config` | `TeamConfigResult` | `agents: list[str]` |
| `task_plan` | `TaskPlanResult` | `tasks: list[PlannedTask]`（id/name/agent/task_type/description/reviewer/dependencies） |
| `evaluate` | `EvaluateResult` | `should_split` / `reason` / `sub_tasks[]` |
| `execute` | `ExecuteResult` | `outcome: Outcome`（kind=artifact\|action + artifact + evidence） |
| `plan` | `PlanResult` | `approach` / `steps[]` / `risks[]` / `confidence` |
| `review` | `ReviewResult` | `passed` / `feedback` / `checklist[]` |
| `triage` | `TriageResult` | `decision: retry\|reassign\|drop\|abort\|split` / `target_agent` / `sub_tasks[]` |
| `skill_review` | `SkillReviewResult` | `action: patch\|reference\|create\|noop` / `skill_id` / `pending_content` |

**共享子结构**：
- `Quality`（Agent 自评，D11：execute/review 强制必填）：`score: 0..1` / `known_gaps[]` / `notes`
- `Meta`（计量/归因，D8）：`model` / `backend` / `tokens`
- `Outcome`（D5/D15）：`kind: artifact|action` + `artifact` + `evidence`（action 类必填硬证据）
- `_BaseResponse`：`interaction_id` / `schema_version` / `status: ok|needs_retry|failed` / `quality` / `meta` / `notes`

**校验入口**：
```python
def parse_response(data: dict)                              # 反序列化，非法抛 ValidationError
def validate_response_dict(data) -> (ok, model, errors)     # submit_result / 框架侧复用
def parse_request(data: dict) -> InteractionRequest
def response_json_schema(kind: str) -> dict                 # 导出 JSON Schema 下发 Agent 本地校验
```

**原则**：结构进代码（Pydantic）；内容约束进配置（`templates.yaml`）；submit_result 在 Agent 侧按引用本地校验后才写回，框架侧用同一模型再校验 → **从根上消灭 JSON 抢救**（D1/F1）。

### 9.2 RunRequest（[adapter/protocol.py](../backend/adapter/protocol.py)）

```python
@dataclass
class RunRequest:
    workspace: str
    message: str
    model: str
    session_id: Optional[str]
    rules_file: Optional[str]
    agent_id: Optional[str]
    cancel_event: Optional[Event]
    extra: dict
```

### 9.3 Process 配置与结果（[process_types.py](../backend/common/process_types.py)）

```python
@dataclass
class ProcessConfig:
    mode: str = "one_shot"               # one_shot | recurring
    max_gate_retries: int = 3            # 确定性门禁失败重试上限（D19 PATCH 减为 3）
    max_plan_retries: int = 2
    review_enabled: bool = False         # 同行评审
    quality_floor: float = 0.6           # 自评低于此 → needs_review
    needs_review_blocks: bool = False    # needs_review 是否阻塞依赖者（默认否，D18）
    token_budget: Optional[int] = None   # per-project token 硬上限（D17）
    budget_alert_ratio: float = 0.8
    budget_degrade_threshold: float = 0.8  # L3 降级触发
    skill_extract_enabled: bool = False
    max_cycles: int = 3                  # recurring 周期上限
    split_enabled: bool = False          # evaluate 拆分
    max_split_depth: int = 2             # 递归拆分深度上限（终止性硬底）
    max_subtasks: int = 8
    parallel_enabled: bool = False       # L2 同波次真并行
    max_parallel: int = 4
    plan_enabled: bool = True            # 路径 A：execute 前插 plan

@dataclass
class TaskOutcome:
    task_id: str
    status: str                          # completed | needs_review | failed | blocked
    reason: str
    attempts: int
    response: Optional[dict]

@dataclass
class ProjectOutcome:
    project_id: str
    status: str                          # completed | partially_failed | failed | aborted
    tasks: dict[str, TaskOutcome]

class BudgetExceededError(Exception)     # 交互级 budget 硬停
```

终端态：`TERMINAL_OK = {"completed", "needs_review"}`；`TERMINAL_BAD = {"failed", "blocked"}`。

---

## 10. 关键类与函数索引

### 10.1 编排内核

| 类/函数 | 文件 | 说明 |
|---------|------|------|
| `Process` | [process.py](../backend/common/process.py) | 项目状态机：`run()` / `resume()` |
| `TaskPipeline` | [task_pipeline.py](../backend/common/task_pipeline.py) | 单任务执行管线（plan/execute/gate/finalize） |
| `DecisionPipeline` | [decision_pipeline.py](../backend/common/decision_pipeline.py) | team_config/task_plan/triage 决策 |
| `PlanExpander` | [plan_expansion.py](../backend/common/plan_expansion.py) | evaluate 拆分 |
| `AgentPort` | [agent_port.py](../backend/common/agent_port.py) | Interaction 投递 + 看门狗 + `.response` 采纳；`run(request)` |
| `WatchdogConfig` / `AgentPortResult` / `DeliveryContext` | [agent_port.py](../backend/common/agent_port.py) | 看门狗与投递上下文 |
| `Gate` 系列函数 | [gate.py](../backend/common/gate.py) | `check_contract` / 格式 / 证据 / 代码项目 |
| `GateResult` | [gate.py](../backend/common/gate.py) | 门禁结果（`passed`/`failures`/`feedback`） |
| `FormatSpec` / `get_spec` / `is_stub` | [registry.py](../backend/common/registry.py) | task_type 约束单一出处 |
| `Store` | [store.py](../backend/common/store.py) | SQLite 真相库（project/task/interaction/run_event/memory） |
| `submit` / `SubmitError` | [submit_result.py](../backend/common/submit_result.py) | Agent 侧交卷 + 派发门 |
| `AdapterTransport` | [agent_transport.py](../backend/common/agent_transport.py) | 构建 worker prompt + 驱动 CLI 适配器 |
| `ProcessConfig` / `ProjectOutcome` / `TaskOutcome` | [process_types.py](../backend/common/process_types.py) | 配置与结果类型 |
| `run_project` / `resume_project` / `resume_in_progress_projects` | [run_kernel.py](../backend/common/run_kernel.py) | 内核入口函数 |
| `run_loop` / `LoopSpec` / `RunLoopDeps` | [loop_runtime.py](../backend/common/loop_runtime.py) | Workflow loop 步骤 |
| `deps_block` / `ready_tasks` / `derive_project_status` | [dag_dispatch.py](../backend/common/dag_dispatch.py) | DAG 调度辅助 |
| `check_plan` / `topological_order` | [plan_gate.py](../backend/common/plan_gate.py) | 规划闸门 |
| `check_budget` / `BudgetConfig` | [observability.py](../backend/common/observability.py) | 预算检查 |

### 10.2 契约与事件

| 类/函数 | 文件 | 说明 |
|---------|------|------|
| `InteractionRequest` / `InteractionResponse` | [contracts.py](../backend/common/contracts.py) | 框架↔Agent 唯一契约 |
| 各 `*Result` / `*Response` | [contracts.py](../backend/common/contracts.py) | 8 种 kind 的 result 与信封 |
| `Quality` / `Meta` / `Outcome` / `Artifact` / `Evidence` | [contracts.py](../backend/common/contracts.py) | 共享子结构 |
| `parse_response` / `validate_response_dict` / `response_json_schema` | [contracts.py](../backend/common/contracts.py) | 校验入口 |
| `CLIAdapter` / `RunRequest` / `AdapterCapabilities` / `ModelInfo` | [adapter/protocol.py](../backend/adapter/protocol.py) | CLI 抽象 |
| `AgentEvent` / `EventKind` | [adapter/events.py](../backend/adapter/events.py) | 统一事件 |
| `AdapterRegistry` / `registry` | [adapter/registry.py](../backend/adapter/registry.py) | 适配器注册中心 |

### 10.3 Hub / Base

| 类/函数 | 文件 | 说明 |
|---------|------|------|
| `lifespan` / `app` | [server.py](../backend/hub/api/server.py) | FastAPI 入口 + 启动恢复 |
| `BackendConfig` / `get_agent_backend_config` | [agent_chat.py](../backend/base/agent_chat.py) | Agent 后端配置 |
| `AgentIdentityBuilder` / `multi_agent_manager` | [agent_identity.py](../backend/base/agent_identity.py) | 身份组装 |
| `generate_agent` / `suggest_agent_id` | [agent_factory.py](../backend/base/agent_factory.py) | Agent 工厂 |
| `run_kernel_bg` / `resume_kernel_bg` / `start_kernel_job` | [project_launch.py](../backend/hub/services/project_launch.py) | 后台启动内核 |
| `system_config` | [store/system_config.py](../backend/store/system_config.py) | 系统配置（端口/backend/model/cli_path） |

---

## 11. 依赖关系

### 11.1 模块依赖方向

```
frontend ──HTTP/SSE──► hub/api ──► hub/services ──► base/agent_chat
                                              │
                                              ▼
                                          adapter/registry ──► adapters/<cli>
                                          adapter/events
                                              │
run_kernel.py ──► common/process ──► common/agent_port ──► common/agent_transport
                       │                    │                      │
                       ▼                    ▼                      ▼
                 common/gate           common/store            adapter/registry
                 common/registry       common/contracts        adapters/<cli>
                 common/dag_dispatch
                       │
                       ▼
                 business/templates/templates.yaml  (Strategy)
                 business/rules/  business/skills/  business/workflows/
```

**关键边界**：
- `hub/services/`、`base/` **不得** import `opencode` 或 `subprocess`（只能通过 `adapter/`）。
- `common/` 内核 **不依赖** Hub（可独立运行）。
- UI **不得**引用 CLI 专属字段。

### 11.2 外部依赖

| 依赖 | 用途 | 安装方式 |
|------|------|----------|
| Python 3.12+ | 运行时 | 系统 |
| `fastapi` / `uvicorn` | Hub API | `pip install -r requirements.txt` |
| `pydantic` | 契约校验 | 同上 |
| `PyYAML` | workflow/templates 解析 | 同上 |
| `python-pptx` | PPT 交付 | 同上 |
| Node.js | 构建 frontend | 系统 |
| **OpenCode CLI** | 默认 CLI 后端 | 外部安装；默认 `~/.opencode/bin/opencode` |
| **Claude CLI**（可选） | 备选 CLI 后端 | 外部安装 |

**CLI 后端是外部依赖**——myteam 不持有模型 token；opencode/claude 须单独安装并配置模型 provider/auth。

### 11.3 Python 包导入约定

`PYTHONPATH=backend` 后按包导入：`from common.process import Process`、`from adapter.protocol import CLIAdapter`、`from store.system_config import system_config`。测试同样需要 `PYTHONPATH=backend`。

---

## 12. 配置与数据落盘

### 12.1 入库 vs gitignore

| 入库（随代码） | gitignore（本机运行态） |
|----------------|-------------------------|
| `business/templates/`、`business/skills/`、`business/workflows/`、`business/rules/`、`backend/`、`frontend/src/`、`scripts/`、`docs/` | `config/*.json`（首次启动自动生成） |
| | `business/config/*`（agents、groups、mcp_registry…） |
| | `business/workspaces/`、`business/tasks/`（含 `state.db`） |
| | `frontend/dist/`、`**/node_modules/` |

### 12.2 关键配置文件

| 文件 | 作用 |
|------|------|
| `config/system_config.json` | 端口、默认 backend/model、OpenCode cli_path、模型列表（首次自动生成） |
| `config/skill_config.json` | 协作/通知等系统开关 |
| `business/config/agents_config.json` | 每 Agent 的 backend、model、workspace 路径 |
| `business/config/agents_registry.json` | 名册：role、task_types、**skills[]**、**mcp_servers[]** |
| `business/config/mcp_registry.json` | 全局 MCP 定义（command/url、enabled） |
| `business/config/groups.json` | 群组 |
| `business/config/session_map.json` | CLI session 映射 |
| `business/tasks/state.db` | 项目/任务/run 真相（SQLite） |

### 12.3 Bootstrap 脚本

```bash
python3 scripts/bootstrap_business_roster.py   # business-roster → registry + workspace
python3 scripts/bootstrap_agent_roster.py      # 仅 Agent 相关 bootstrap
```

---

## 13. 项目运行方式

### 13.1 安装

```bash
cd myteam
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

cd frontend && npm install && npm run build && cd ..
```

### 13.2 启动 Hub

```bash
./run.sh start    # http://localhost:8765 → /v2/，binds 0.0.0.0，uvicorn reload=True
./run.sh stop
```

`run.sh` 设置 `MYTEAM_ROOT`、`PYTHONPATH=backend`，执行 [backend/hub/api/server.py](../backend/hub/api/server.py)。

### 13.3 启动编排内核（可不启 Hub）

```bash
export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend" NO_PROXY="localhost,127.0.0.1,::1"
venv/bin/python3 backend/common/run_kernel.py <project_id> \
  --goal "你的目标" --mode one_shot --budget 150000 \
  [--max-cycles 3] [--review] [--split] [--workflow <ID>]
# exit 0 only when status == completed
```

使用 Claude CLI 后端：

```bash
venv/bin/python3 backend/common/run_kernel.py <project_id> \
  --goal "..." --backend claude --budget 150000
```

断点续跑 / demo / 初始化：

```bash
venv/bin/python3 backend/common/run_kernel.py <project_id> --resume --backend opencode
venv/bin/python3 backend/common/run_kernel.py --demo
venv/bin/python3 backend/common/run_kernel.py --init   # 为所有注册 agent 创建 workspace（幂等）
```

冒烟：

```bash
venv/bin/python3 backend/common/run_kernel.py smoke_test \
  --goal "为 example.com 做一次 GEO 快速评估" --budget 80000
```

### 13.4 测试

```bash
# 全量
PYTHONPATH="$PWD/backend" venv/bin/python3 -m pytest backend -q
# 或
./scripts/test.sh

# 单测
PYTHONPATH="$PWD/backend" venv/bin/python3 -m pytest \
  backend/common/tests/test_gate.py::test_registry_loads_real_types -q
```

测试覆盖约 80+ 个 `test_*.py`（Gate、Process、Skill、MCP、API 契约、adapter parser 等）。`PYTHONPATH=backend` 必填——测试 import `common`/`hub` 包。无 linter/formatter（无 ruff/black/mypy/Makefile）。

### 13.5 使用入口

| 场景 | 入口 |
|------|------|
| 私聊 Agent | `/v2/chat` |
| 群聊 @Agent | `/v2/groups` |
| 管理 Agent / 挂 Skill·MCP | `/v2/manage` |
| 注册 MCP | `/v2/mcp` → 启用 → Agent 勾选 → 同步 MCP |
| 编辑 Workflow | `/v2/workflows` |
| 跑项目 / 看 DAG | `/v2/projects` 或 `run_kernel.py` |
| 可观测 | `/api/obs/...` 或项目页时间线 |

---

## 14. 不变量与设计决策

### 14.1 必须遵守的不变量

**适配器隔离**（`docs/ARCHITECTURE.md` §10）：
- `adapters/<cli>/parser.py` 是**唯一**允许知道 CLI 原始输出格式的地方。
- 服务层（`hub/services/`、`base/`）不得包含 `opencode` 或 `subprocess`。
- UI 不得引用 CLI 专属字段，只消费 `thinking` SSE 事件的 `type`。
- 新增 CLI = 新 `adapters/<cli>/` 目录 + parser + 更新 `agent_transport._default_adapter()`，无需改 UI。

**Interaction 契约**（[contracts.py](../backend/common/contracts.py)，D11/D5/D15）：
- 框架与 Agent 只交换 `InteractionRequest` / `InteractionResponse` 一对模型。
- 结构进代码（Pydantic），内容约束进配置（`templates.yaml`）。
- `submit_result` 在 Agent 侧本地校验后才写 `.response`；**无 JSON 抢救/修复路径**——非法输出被拒绝而非挽救（D1/F1）。
- `Gate` 用**同一** registry spec 校验（`registry.get_spec(task_type)`）——下发与检查共用一源。

### 14.2 设计决策（D1–D19 / F1，散见代码注释与 `docs/framework-decisions.md`）

| 决策 | 含义 |
|------|------|
| D1 / F1 | 契约路径是唯一路径；删除 JSON 抢救与 `INTERACTION_CONTRACTS` 迁移开关 |
| D5 / D15 | Outcome = Artifact ∪ Action；一个 task_type 只有一个主 kind；action 类必填硬证据 |
| D7 | 两段式看门狗（soft_idle 疑似卡死 / hard_idle 取消+重试） |
| D8 | 幂等/残留治理：按 interaction_id 命名；启动对账 GC |
| D10 | 单内核 + 模式配置（one_shot / recurring），合并旧双引擎 |
| D11 | 结构进代码、内容约束进配置；execute/review 强制 quality 自评 |
| D12 | AgentPort 串行投递；文件做缓存，store 做真相 |
| D13 | 运行态状态 = SQLite（真相）；task_data.json 退为只读导出视图 |
| D14 | Gate 只判契约 + 格式 + 完整性；质量归 Agent |
| D16 | 注入直接上游摘要 + 引用（上下文传播） |
| D17 | per-project token 硬上限 |
| D18 | 失败语义：failed（阻塞）/ needs_review（默认不阻塞）；升级阶梯 → 委托 Main triage |
| D19 | max_gate_retries 减为 3 |

### 14.3 三层决策规则

| 判断 | 落点 |
|------|------|
| 失败会污染系统状态（需持久化/重试/审计） | System Kernel |
| 改 task_type / 角色选择 / 验收 | Strategy Registry |
| 只影响单次任务质量 | Skill |

**新增 task_type 必须先改 [templates.yaml](../business/templates/templates.yaml)**；只写 Skill 无法让 Process 识别任务。

### 14.4 编辑约定（[.cursor/rules/karpathy-guidelines.mdc](../.cursor/rules/karpathy-guidelines.mdc)）

- 最小代码解决问题（无投机抽象/配置）；
- 外科手术式改动（只碰请求所需，匹配既有风格，不重构工作代码，不删既有死代码）；
- 实现前先抛出假设与权衡；
- 定义可验证的成功标准（写/跑测试）而非「让它能跑」。

提交风格：中文 conventional-commit（`feat(ux):`、`fix(reliability):`、`refactor(css):`、`polish(ui):`、`docs(architecture):`）。

---

## 15. 易混淆项速查

| 名称 | 实际含义 |
|------|----------|
| `backend/store/` | **JSON 配置**读写（system_config），**不是** SQLite |
| `backend/common/store.py` | **SQLite** 项目真相库 |
| `business/skills/` | Skill **源库**；Hub 同步到 `.opencode/skills/` |
| `skill/`（`common/paths.py` 内 `TEAM_SKILL_DIR`） | 历史路径常量；当前仓库根下**无** `skill/` 目录 |
| `frontend/` vs `frontend/` | v1 经典静态页（默认关闭）vs v2 生产 SPA |
| 删除 MCP registry 条目 | 只取消 Hub 挂载与 workspace 同步；**不**卸载本机 npm 包 |
| workflow `roster` 键 | **不存在**；roster 是独立 JSON，workflow 用 `agent_id` 引用 |
| `outcome_kind` | `templates.yaml` 中显式声明者统一为 `artifact`；action 类由 evidence_url 配置触发 |
| `research` 角色 id | 研究员角色 id 是 **`research`**（legacy `researcher` 已废弃） |
| `base/system_config.py` | deprecated shim，re-export `store.system_config` |

### 故障排查

| 现象 | 处理 |
|------|------|
| OpenCode CLI 未找到 | 安装 opencode 或设 `OPENCODE_CLI_PATH` / `system_config.backends.opencode.cli_path` |
| `/v2` 空白 | `cd frontend && npm run build` |
| 看不到项目进度 | 确认 `business/tasks/state.db` 存在且 Hub 与 kernel 共用同一 `MYTEAM_ROOT` |
| MCP 不生效 | MCP 页启用 → Agent 勾选 →「同步 MCP」→ 检查 workspace 内 `opencode.json` |
| Agent 私聊无 Skill 摘要 | 检查 `agents_registry.json` 的 `skills`；Skill 的 `description` 在 SKILL.md frontmatter |

---

**文档版本**：2026-06-26，与仓库源码同步。若发现与代码不符，以 `backend/`、`frontend/src/`、`business/templates/` 为准。
