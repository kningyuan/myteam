# myteam

轻量级 **多 Agent 协作平台**：Web Hub（私聊 / 群聊 / Agent 管理 / Skill / MCP / Workflow / 项目可观测）+ 声明式编排内核（把 `goal` 拆成任务 DAG，按 wave 调度多 Agent，Gate 校验、重试、triage）。

Agent 执行通过 **CLI 适配器**驱动（生产默认 **OpenCode**；另有 **Claude CLI** 适配器与 **stub** 测试后端）。

> 深度设计文档见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)、[`docs/FRAMEWORK_BOUNDARY.md`](docs/FRAMEWORK_BOUNDARY.md)、[`frontend-v2/ARCHITECTURE.md`](frontend-v2/ARCHITECTURE.md)。文档索引 [`docs/README.md`](docs/README.md)。

---

## 目录

1. [整体架构](#1-整体架构)
2. [交互架构（Hub ↔ CLI ↔ 内核）](#2-交互架构hub--cli--内核)
3. [后端架构](#3-后端架构)
4. [前端架构](#4-前端架构)
5. [配置与数据落盘](#5-配置与数据落盘)
6. [安装与启动](#6-安装与启动)
7. [使用方式](#7-使用方式)
8. [测试](#8-测试)
9. [仓库目录与文件说明](#9-仓库目录与文件说明)

---

## 1. 整体架构

### 1.1 两条正交流

```
A) Hub 交互流（人 ↔ Agent / 群）
   浏览器 frontend-v2 (/v2)
     → FastAPI backend/hub/api/server.py
     → hub/services/chat_service（或 groups / notify）
     → base/agent_chat + adapter/registry
     → adapters/opencode | adapters/claude（子进程 CLI）
     → 统一 AgentEvent → SSE 推前端

B) 编排内核流（目标 → 多 Agent 自动交付）
   run_kernel.py 或 Hub「运行项目」
     → common/process.py（状态机）
     → common/agent_port.py（Interaction 投递 + submit_result 收卷）
     → common/gate.py（确定性验收）
     → SQLite business/tasks/state.db（真相）
     → 交付物 business/tasks/project/<id>/deliverables/
```

两条流 **共用** Agent 名册、Skill/MCP 挂载、workspace、SQLite；**编排不依赖 Hub 进程**（Hub 只读同一库做可观测）。

### 1.2 三层职责（System / Strategy / Skill）

| 层 | 路径 | 职责 |
|----|------|------|
| **System Kernel** | `backend/common/`、`backend/adapter/`、`backend/hub/` | Process、AgentPort、Gate、Store、contracts、Hub API、CLI 适配 |
| **Strategy Registry** | `business/templates/`、`business/config/agents_registry.json`、`business/workflows/`、`business/rules/` | task_type、prompt 壳、workflow、名册、验收规则 |
| **Skill / MCP Pack** | `business/skills/*/SKILL.md`、`business/config/mcp_registry.json` | 具体执行方法论；MCP 工具目录 |

**决策规则**：需要持久化、重试、审计 → Kernel；改 task_type / 角色 / 验收 → Registry；单次执行质量 → Skill。

### 1.3 路径与环境变量

| 变量 | 作用 |
|------|------|
| `MYTEAM_ROOT` | 仓库根目录（`run.sh` 自动设为当前目录） |
| `PYTHONPATH` | 须包含 `backend/`（`run.sh` 自动设置） |
| `LOCAL_AGENT_PORT` | Hub 端口，默认 `8765` |
| `OPENCODE_CLI_PATH` | 覆盖 OpenCode 可执行文件路径 |
| `MYTEAM_V1_UI=1` | 临时开放经典 UI `frontend/`（默认关闭） |

路径常量：**Hub 侧** `backend/hub/paths.py`；**内核侧** `backend/common/paths.py`（二者均相对 `MYTEAM_ROOT`）。

---

## 2. 交互架构（Hub ↔ CLI ↔ 内核）

### 2.1 私聊（DM）

```
GET /api/chat/{agent_id}?message=...
  → chat_service.stream(use_memory=True)
  → 每轮注入 build_skill_context + build_mcp_context（读 agents_registry，非 AGENTS.md）
  → merge_rules_file(profile=interactive) → 临时 rules 文件
  → adapter.run(RunRequest) → opencode run --dir workspace-{id} ...
  → SSE: data: {"event":"token"|"tool"|...}\n\n
```

Skill/MCP **边界摘要**每轮注入；**完整 SKILL.md** 仅在 Agent 主动 Read 时进入上下文。MCP **工具 schema** 由 CLI 进程加载，不写入 Hub prompt。

### 2.2 群聊 / 圆桌

```
/api/groups/* → group_manager + group_broadcast
  → 多 Agent 串行/讨论 loop（loop_discussion_*）
  → 同样走 adapter，rules_profile=discussion
```

### 2.3 编排 execute / review / triage

```
Process 调度 wave
  → agent_port.run(InteractionRequest)
  → agent_transport.build_worker_prompt（注入 task_type、Gate、Skill/MCP、上游摘要）
  → CLI 子进程执行
  → Agent 调用 submit_result.py → workspace/.response/{interaction_id}.response
  → Gate 校验 → 通过 / retry_feedback / triage
```

Agent **不互读** `.trigger`；协作靠 **DAG 依赖 + 交付物路径 + 上游 summary**。

### 2.4 Workspace 交卷通道

每个 Agent 工作区（`business/workspaces/workspace-{agent_id}/`，gitignore 运行态）：

| 路径 | 作用 |
|------|------|
| `AGENTS.md` / `IDENTITY.md` / `SOUL.md` / `USER.md` | 人设与规则；execute 时 rules 会合并 AGENTS.md |
| `.trigger/{interaction_id}.request` | Interaction 请求快照（审计）；CLI 由内存 prompt 驱动 |
| `.response/{interaction_id}.response` | `submit_result` 原子写入的契约 JSON |
| `.opencode/skills/{id}/` | Hub 同步的 Skill 符号链接（OpenCode） |
| `opencode.json` | Hub 同步的 MCP 块（OpenCode） |
| `.opencode/.myteam-mcp.json` | myteam 记录的 MCP 挂载清单 |

**不再**向 AGENTS.md 自动写入 `## 已挂载 Skill/MCP`（历史段落会在保存/启动时被 strip）。

### 2.5 Skill / MCP 配置链

```
UI 勾选 / MCP 页编辑
  → business/config/agents_registry.json（skills[]、mcp_servers[]）
  → business/config/mcp_registry.json（全局 MCP 目录 + enabled）
  → adapter.sync_agent_skills / sync_agent_mcp
  → workspace 内 .opencode/skills、opencode.json
  → 每轮 chat/execute：build_skill_context / build_mcp_context 注入摘要
```

---

## 3. 后端架构

单棵 Python 树 `backend/`，`PYTHONPATH=backend` 后按包导入。

### 3.1 分层

```
hub/api/          FastAPI 薄路由（server.py 入口 + routes/* + skills_api + mcp_api + observability_api）
hub/services/     聊天、群组、项目启动、SSE、Agent 注册表业务
base/             Agent 工厂、身份组装、群管理、agents_config 读写
adapter/          CLIAdapter 抽象、AgentEvent、SSE 编码、registry
adapters/         opencode | claude | stub_cli 具体实现
store/            系统级 JSON 配置（system_config、skill_config、sessions）
common/           编排内核 + 共享领域（Process、AgentPort、Gate、Store SQLite、Skill/MCP catalog）
```

### 3.2 Hub API 路由聚合

| 模块 | 前缀 / 路径 | 职责 |
|------|-------------|------|
| `routes/chat.py` | `/api/chat` | DM SSE、cancel、status |
| `routes/groups.py` | `/api/groups` | 群 CRUD、消息、@mention |
| `routes/agents.py` | `/api/agents` | 名册、backend/model、Skill/MCP 挂载 |
| `routes/projects.py` | `/api/projects` | 创建/运行/取消项目、交付物 |
| `routes/workflows.py` | `/api/workflows` | Workflow YAML CRUD、校验 |
| `routes/config.py` | `/api/...` | sync-skills、sync-mcp、task-types 等 |
| `routes/jobs.py` | `/api/jobs` | 后台 job |
| `routes/channels.py` | `/api/channels` | 通知渠道 |
| `routes/workspace_events.py` | `/api/workspace-events` | 工作区事件 SSE |
| `skills_api.py` | `/api/skills` | Skill 库 CRUD、章节、文件 |
| `mcp_api.py` | `/api/mcp` | MCP 库 CRUD、enabled |
| `observability_api.py` | `/api/obs` | 项目/Agent 可观测、run_event SSE |
| `server.py` 直连 | `/api/status`、`/api/task-types`、`/api/delivery-templates`、`/api/init` 等 | 杂项与遗留端点 |

静态资源：`/` → 重定向 `/v2/`；`frontend-v2/dist` 作为 SPA；`frontend/` 仅 `MYTEAM_V1_UI=1` 时可访问 `/classic`。

### 3.3 CLI 适配器

| 文件 | 作用 |
|------|------|
| `adapter/protocol.py` | `CLIAdapter`、`RunRequest`、`sync_agent_skills/mcp` 默认空实现 |
| `adapter/registry.py` | 后端 id → 适配器实例 |
| `adapters/opencode/adapter.py` | `opencode run` 子进程、严格 Skill 环境变量 |
| `adapters/opencode/skill_sync.py` | 工作区 `.opencode/skills` 符号链接 |
| `adapters/opencode/mcp_sync.py` | 写 `opencode.json` MCP 块 |
| `adapters/opencode/parser.py` | OpenCode JSON 行 → AgentEvent |
| `adapters/claude/adapter.py` | Claude CLI 包装（MCP sync 默认 no-op） |
| `adapters/stub_cli.py` | 测试用假 CLI |

### 3.4 编排内核（`backend/common/` 按域）

**入口与状态机**

| 文件 | 作用 |
|------|------|
| `run_kernel.py` | CLI 入口：组装 Store + AgentPort + Process |
| `process.py` | 项目状态机：team_config → task_plan → wave 调度 |
| `process_types.py` | Process 相关类型 |
| `agent_port.py` | Interaction 投递、看门狗、`.response` 采纳 |
| `agent_transport.py` | 构建 team_config/task_plan/execute worker prompt |
| `submit_result.py` | Agent 侧交卷 CLI + 契约校验入口 |
| `gate.py` / `quality_gate.py` / `plan_gate.py` | 交付 Gate、规划 Gate |
| `store.py` / `store_sqlite.py` / `store_backend.py` | SQLite 真相库抽象与实现 |

**Agent / Skill / MCP**

| 文件 | 作用 |
|------|------|
| `agent_registry.py` | 读 `agents_registry.json` |
| `agent_skills.py` | Skill 挂载解析、`build_skill_context`、strip AGENTS.md Skill 节 |
| `agent_mcp.py` | MCP 挂载解析、`build_mcp_context`、strip AGENTS.md MCP 节 |
| `skill_catalog.py` | 扫描 `business/skills/*/SKILL.md` |
| `mcp_catalog.py` | 读写 `business/config/mcp_registry.json` |
| `adapter_skill_registry.py` | 批量 sync Skill 到 CLI |
| `adapter_mcp_registry.py` | 批量 sync MCP 到 CLI |
| `skill_extract.py` / `skill_methodology.py` | Skill 草案抽取与方法论 |
| `agent_model.py` | agents_config 与 registry 对齐 |
| `agent_bootstrap.py` | 创建 Agent workspace |
| `agent_execution.py` | Agent 执行锁（chat vs kernel 互斥） |
| `agent_memory.py` | DM 记忆 scope / provider |
| `agent_id_policy.py` | Agent id 命名策略 |

**Workflow / task_type / 交付**

| 文件 | 作用 |
|------|------|
| `workflow_loader.py` / `workflow_validate.py` | 加载校验 `business/workflows/*.yaml` |
| `workflow_bootstrap.py` / `workflow_suggest.py` | Workflow 引导与建议 |
| `workflow_capability_bind.py` / `workflow_collaboration.py` | 能力与协作绑定 |
| `registry.py` | `templates.yaml` → task_type spec |
| `task_type_store.py` / `task_type_suggest.py` | task_type CRUD / 建议 |
| `delivery_templates.py` / `delivery_template_store.py` | 交付模板 |
| `delivery_profiles.py` / `deliverable_guarantee.py` | 交付形态与骨架保证 |
| `prompt_templates.py` / `prompt_composer.py` / `prompt_injections.py` | Execute 等 prompt 壳 |
| `rules_merge.py` | 合并 universal/worker/AGENTS rules 文件 |

**项目运行时 / 可观测**

| 文件 | 作用 |
|------|------|
| `project_runtime.py` / `project_admin.py` / `project_cancel.py` | 项目生命周期 |
| `project_artifacts.py` / `project_hooks.py` / `kernel_project_hooks.py` | 产物与 hook |
| `project_group_discussion.py` | 项目内群讨论 |
| `observability.py` / `token_usage.py` / `audit_log.py` | 指标、token、审计 |
| `job_supervisor.py` | 孤儿 job 检测 |
| `workspace_gc.py` / `workspace_events.py` | workspace 清理与事件 |
| `recurring_trigger.py` |  recurring 模式触发 |

**Loop / 圆桌 / 讨论**

| 文件 | 作用 |
|------|------|
| `loop_runtime.py` | Workflow 内 loop 步骤 |
| `loop_discussion_runtime.py` / `loop_discussion_dispatch.py` | 讨论型 loop |
| `roundtable_runtime.py` / `roundtable_context.py` | 圆桌编排 |
| `group_message_store.py` | 群消息持久化辅助 |

**其它 common 模块**

| 文件 | 作用 |
|------|------|
| `paths.py` | 内核路径常量（MYTEAM_ROOT、workspaces、tasks…） |
| `contracts.py` | InteractionRequest/Response JSON Schema |
| `config.py` / `kernel_config.py` | 内核配置读取 |
| `dag_dispatch.py` / `decision_pipeline.py` / `plan_expansion.py` / `plan_splice.py` | DAG 与规划辅助 |
| `context_assembler.py` / `memory.py` | 对话上下文组装 |
| `experience.py` | 经验 ledger |
| `event_handler.py` / `notify_format.py` / `ops_log.py` / `logger.py` | 事件与日志 |
| `goal_template.py` / `business_hook_loader.py` | goal 模板与业务 hook |
| `hub_operation_meta.py` | Hub 操作元数据 |
| `thinking_trace.py` | 思考链持久化 |
| `task_pipeline.py` / `task_data_store.py` | 任务管线与 task_data.json |

**测试**：`backend/common/tests/`（约 80+ 个 `test_*.py`，覆盖 Gate、Process、Skill、MCP、API 契约等）。`backend/hub/services/tests/` 含 `test_stream_fanout.py`。

---

## 4. 前端架构

生产 UI：**`frontend-v2/`**（React 19 + Vite 8 + TypeScript + Tailwind 4 + React Router 7）。构建产物 `frontend-v2/dist/`（gitignore），Hub 在 `/v2` 提供 SPA。

经典 UI：**`frontend/`**（纯静态 HTML/JS），默认不对外；设置 `MYTEAM_V1_UI=1` 后访问 `/classic`。

### 4.1 分层（详见 `frontend-v2/ARCHITECTURE.md`）

```
App.tsx (BrowserRouter basename=/v2)
  → Sections（功能页：ChatSection、ManageSection…）
  → Components（project/、chat/、workflow/、skills/、mcp/…）
  → Hooks（useAgentChat、useResourceQuery）
  → Ports（ChatPort、ProjectsPort — 可替换实现）
  → lib/api/*（薄 HTTP 客户端）
  → Hub REST /api/*
```

### 4.2 路由（`App.tsx`）

| 路径 | Section / Page |
|------|----------------|
| `/v2/` | Dashboard |
| `/v2/chat/:agentId?` | 私聊 |
| `/v2/groups/:groupId?` | 群聊 |
| `/v2/projects/:projectId?` | 项目列表与详情 |
| `/v2/manage/:tab?/:itemId?` | Agent / 后端 / 任务类型等管理 |
| `/v2/workflows/:workflowId?` | Workflow 编辑器 |
| `/v2/skills/:draftId?` | Skill 库 |
| `/v2/mcp/:serverId?` | MCP 库 |
| `/v2/settings/:section?` | 系统设置 |

主导航定义在 `components/layout/DiscordShell.tsx`（RailNav）。

### 4.3 API 客户端（`src/lib/api/`）

| 文件 | 职责 |
|------|------|
| `client.ts` | `hubFetch`、SSE 流、错误处理 |
| `agents.ts` | Agent CRUD、sync skills/mcp |
| `chat.ts` | DM chat |
| `groups.ts` | 群组 |
| `projects.ts` | 项目 + `/api/obs/projects` |
| `workflows.ts` | Workflow、task-types、delivery-templates |
| `mcp.ts` | MCP library |
| `config.ts` | backends、obs summary |
| `index.ts` |  barrel 重导出 |

`lib/dataRefresh.ts`：跨组件资源失效广播（如 `"mcp-library"`）。

### 4.4 前端源码文件一览

**入口与样式**：`main.tsx`、`App.tsx`、`App.css`、`index.css`

**Pages**（`src/pages/`）：`DashboardPage`、`AgentsPage`、`GroupChatPage`、`GroupsPage`、`ProjectDetailPage`、`ProjectsPage`、`SettingsPage`、`TaskTypesPage`、`WorkflowsPage`

**Sections**（`src/sections/`）：`ChatSection`、`GroupsSection`、`ManageSection`、`ProjectsSection`、`SettingsSection`、`SkillsSection`、`McpSection`、`WorkflowsSection`

**Components**（节选）：

- `layout/`：`DiscordShell`、`AppShell`、`ListItemRow`、`ListNavItem`
- `chat/`：`AgentChatPanel`、`GroupMessageBubble`、`ThinkingStream`
- `project/`：`ProjectDag`、`ProjectTimeline`、`ProjectDeliverablePanel`、`ProjectDetailPanel` 等
- `workflow/`：`WorkflowEditor`、`LoopEditorPanel`、`AssessStepEditor` 等
- `skills/`：`SkillDetailPanel`
- `mcp/`：`McpDetailPanel`
- `manage/`：`AgentEditDialog`（含 Skill/MCP 勾选）
- `ui/`：shadcn 风格基础组件（`button`、`dialog`、`tabs`…）
- `MarkdownBody.tsx`

**Hooks**：`useAgentChat.ts`、`useResourceQuery.ts`

**Lib**：`agentChatStream.ts`、`groupChatLive.ts`、`markdown.ts`、`theme.tsx`、`thinking.ts`、`agentLabels.ts`、`project-labels.ts` 等

**Ports**：`ChatPort.ts`、`hubChatPort.ts`、`ProjectsPort.ts`、`hubProjectsPort.ts`

---

## 5. 配置与数据落盘

### 5.1 入库 vs gitignore

| 入库（随代码） | gitignore（本机运行态） |
|----------------|-------------------------|
| `config/` 模板逻辑、`business/templates/`、`business/skills/`、`business/workflows/`、`business/rules/` | `config/*.json`（首次启动自动生成） |
| `backend/`、`frontend-v2/src/`、`scripts/`、`docs/` | `business/config/*`（agents、groups、mcp_registry…） |
| | `business/workspaces/`、`business/tasks/`（含 `state.db`） |
| | `frontend-v2/dist/`、`**/node_modules/` |

### 5.2 关键配置文件

| 文件 | 作用 |
|------|------|
| `config/system_config.json` | 端口、默认 backend/model、OpenCode cli_path |
| `config/skill_config.json` | 协作/通知等系统开关 |
| `business/config/agents_config.json` | 每 Agent 的 backend、model、workspace 路径 |
| `business/config/agents_registry.json` | 名册：role、task_types、**skills[]**、**mcp_servers[]** |
| `business/config/mcp_registry.json` | 全局 MCP 定义（command/url、enabled） |
| `business/config/groups.json` | 群组 |
| `business/config/session_map.json` | CLI session 映射 |
| `business/tasks/state.db` | 项目/任务/run 真相（SQLite） |

模板/bootstrap：

```bash
python3 scripts/bootstrap_business_roster.py   # business-roster → registry + workspace
python3 scripts/bootstrap_agent_roster.py      # 仅 Agent 相关 bootstrap
```

---

## 6. 安装与启动

### 6.1 依赖

| 依赖 | 说明 |
|------|------|
| Python 3.12+ | 推荐 venv：`.venv/` 或 `venv/` |
| `requirements.txt` | fastapi、uvicorn、pydantic、PyYAML、python-pptx |
| Node.js | 构建 `frontend-v2` |
| **OpenCode CLI** | 外部安装；默认 `~/.opencode/bin/opencode` 或 `system_config.backends.opencode.cli_path` |

### 6.2 启动 Hub

```bash
cd myteam
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

cd frontend-v2 && npm install && npm run build && cd ..

./run.sh start    # http://localhost:8765 → /v2/
./run.sh stop
```

`run.sh` 设置 `MYTEAM_ROOT`、`PYTHONPATH=backend`，执行 `backend/hub/api/server.py`。

### 6.3 启动编排内核（可不启 Hub）

```bash
export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend"
.venv/bin/python3 backend/common/run_kernel.py <project_id> \
  --goal "你的目标" --mode one_shot --budget 150000
```

---

## 7. 使用方式

| 场景 | 入口 |
|------|------|
| 私聊 Agent | `/v2/chat` |
| 群聊 @Agent | `/v2/groups` |
| 管理 Agent / 挂 Skill·MCP | `/v2/manage` |
| 注册 MCP（如 Playwright） | `/v2/mcp` → 启用 → Agent 勾选 → 同步 MCP |
| 编辑 Workflow | `/v2/workflows` |
| 跑项目 / 看 DAG | `/v2/projects` 或 `run_kernel.py` |
| 可观测 | `/api/obs/...` 或项目页时间线 |

冒烟：

```bash
.venv/bin/python3 backend/common/run_kernel.py smoke_test \
  --goal "为 example.com 做一次 GEO 快速评估" --budget 80000
```

---

## 8. 测试

```bash
export PYTHONPATH="$PWD/backend"
.venv/bin/python3 -m pytest backend -q
# 或
./scripts/test.sh
```

回归脚本在 `scripts/regression/`（workflow E2E、Gate、Skill API 等）。

---

## 9. 仓库目录与文件说明

以下描述 **当前仓库内实际存在的顶层与源码树**（不含 gitignore 的运行态 workspace 内容、不含 `node_modules`）。

```
myteam/
├── README.md                 # 本文件
├── CLAUDE.md                 # Claude Code 工作区说明（若使用）
├── requirements.txt          # Python 依赖
├── run.sh                    # Hub start/stop；设 MYTEAM_ROOT、PYTHONPATH
├── .gitignore
├── .cursorrules              # Cursor 规则
├── .cursor/rules/            # 项目级 Cursor rules（如 karpathy-guidelines）
├── .github/workflows/test.yml # CI：pytest
│
├── config/                   # 系统配置目录（*.json 通常 gitignore，运行时生成）
│   ├── system_config.json    # [运行态] 端口、backend、模型
│   └── skill_config.json     # [运行态] 系统级 Skill/协作开关
│
├── backend/                  # 全部 Python 后端（见 §3）
│   ├── hub/                  # FastAPI Hub
│   ├── base/                 # Agent 身份、工厂、群
│   ├── adapter/              # CLI 抽象
│   ├── adapters/             # opencode / claude / stub
│   ├── store/                # system_config、skill_config、sessions JSON
│   └── common/               # 编排内核 + 共享域 + tests/
│
├── frontend-v2/              # 生产 Web UI（React SPA，见 §4）
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── public/               # favicon、icons
│   ├── dist/                 # [构建产物，gitignore]
│   ├── ARCHITECTURE.md       # 前端分层说明
│   ├── DESIGN.md             # UI 设计笔记
│   └── src/                  # 源码（见 §4.4）
│
├── frontend/                 # 经典 v1 UI（静态文件，默认关闭）
│   ├── index.html
│   ├── app.js, chat.js, group.js, project.js, manage.js, …
│   └── *.css                 # layout、pages、tokens 样式
│
├── business/                 # 业务领域（配置与运行态混合；见 .gitignore）
│   │
│   ├── templates/            # Strategy 模板（入库）
│   │   ├── templates.yaml           # task_type 格式、Gate、证据规则（权威）
│   │   ├── prompt_templates.yaml    # execute/review 等 prompt 壳
│   │   ├── prompt_injections.yaml   # 条件注入片段
│   │   ├── delivery_profiles.yaml   # 交付形态 profile
│   │   ├── business-roster.json     # 17 角色名册模板
│   │   ├── mcp_registry.template.json # MCP registry 首次 bootstrap 模板
│   │   ├── pgd-agents.json          # PGD 角色边界参考
│   │   └── README.md
│   │
│   ├── rules/                # Agent rules 合并源（入库）
│   │   ├── universal-rules.md       # 全员规则
│   │   ├── interactive-guide.md     # 私聊/群聊 profile
│   │   ├── brainstorming-guide.md   # 讨论 profile
│   │   └── worker-template.md       # execute profile 工人模板
│   │
│   ├── skills/               # Skill 能力包（入库，每目录一个 SKILL.md）
│   │   ├── README.md
│   │   ├── catalog.yaml             # Skill 分类索引
│   │   ├── acceptance-report/       # 各子目录均含 SKILL.md（+ 可选 templates/）
│   │   ├── arch-research/
│   │   ├── architecture-review/
│   │   ├── backend-engineering-methodology/
│   │   ├── code-deliverable/
│   │   ├── code-review/
│   │   ├── code-testing/
│   │   ├── code-writing/
│   │   ├── content/
│   │   ├── coordination-methodology/
│   │   ├── decision-record/
│   │   ├── deck-build/
│   │   ├── diagram-build/
│   │   ├── frontend-architecture-methodology/
│   │   ├── frontend-engineering-methodology/
│   │   ├── hub-ui-debug/
│   │   ├── myteam-config-linkage/
│   │   ├── officecli/
│   │   ├── product-methodology/
│   │   ├── product-operations/
│   │   ├── product-planning/
│   │   ├── product-research/
│   │   ├── publish-post/
│   │   ├── qa-methodology/
│   │   ├── requirements/
│   │   ├── research/
│   │   ├── section-authoring/
│   │   ├── section-review/
│   │   ├── strategy/
│   │   ├── system-architecture-methodology/
│   │   ├── system-design/
│   │   ├── test-plan/
│   │   ├── wps-deck/
│   │   ├── xhs-operations/
│   │   ├── zhihu-operations/
│   │   ├── auto-p-t1/               # auto-* 为 Skill 抽取草案（不可挂载）
│   │   ├── auto-p_demo-t1/
│   │   └── auto-p_wf-t1/
│   │
│   ├── workflows/            # 声明式 Workflow YAML + goal 示例（入库）
│   │   ├── README.md
│   │   ├── README-产品研发.md
│   │   ├── README-platform-v3.md
│   │   ├── profiles/work-review-alignment.yaml
│   │   ├── _examples/iteration-v2-fixture.yaml
│   │   ├── 区块链产品规划-完善.yaml
│   │   └── *.txt                    # 各 workflow 配套 goal 示例文本
│   │
│   ├── delivery_templates/   # 交付物 Markdown/HTML 模板
│   │   └── _examples/
│   │
│   ├── playbooks/            # 人类可读 playbook（ALL.md 等）
│   ├── means/                # 「手段」资产（如 diagram-build 说明）
│   ├── experience/           # 经验 ledger schema + examples
│   ├── agent-catalog/        # Agent 目录说明与 product 子目录
│   ├── demo/                 # demo 用 agents_config + goal.txt
│   ├── hooks/                # 业务 Python hook（如 work_review_alignment.py）
│   ├── regression/           # 回归结果 JSON/JSONL（artifacts/ gitignore）
│   │
│   ├── config/               # [gitignore 运行态] agents_registry、mcp_registry、groups…
│   ├── workspaces/           # [gitignore] workspace-{agent_id}/ 见 §2.4
│   └── tasks/                # [gitignore] state.db + project/{id}/
│
├── scripts/                  # 运维与回归脚本（入库）
│   ├── bootstrap_business_roster.py
│   ├── bootstrap_agent_roster.py
│   ├── audit_skill_matrix.py
│   ├── audit_sqlite_direct_writes.py
│   ├── test.sh
│   ├── test_group_chat_stability.py
│   ├── agent_roundtable_v1.py
│   ├── run_roundtable_test.py
│   ├── lint_workflows_no_skill.sh
│   └── regression/           # reg_*.py、run_regression.sh、tier_e2e.py 等
│
└── docs/                     # 设计/决策/升级文档（入库，非运行必需）
    ├── README.md             # 文档索引
    ├── ARCHITECTURE.md       # 架构详解
    ├── FRAMEWORK_BOUNDARY.md
    ├── DESIGN-SKILL-SYSTEM.md
    ├── V1_CAPABILITY_PLAN.md
    ├── framework-decisions.md
    ├── 0608/                 # 2026-06 升级系列
    ├── 0614/                 # Workflow V2 系列
    ├── new/                  # 需求与映射
    ├── plans/                # 实施计划
    ├── decisions/            # ADR
    ├── assessments/          # 评估记录
    ├── executions/           # 执行变更记录
    └── reports/              # 验收报告
```

### 9.1 易混淆项

| 名称 | 实际含义 |
|------|----------|
| `backend/store/` | **JSON 配置**读写（system_config），不是 SQLite |
| `backend/common/store.py` | **SQLite** 项目真相库 |
| `business/skills/` | Skill **源库**；Hub 同步到 `.opencode/skills/` |
| `skill/`（`common/paths.py` 内 `TEAM_SKILL_DIR`） | 历史路径常量；**当前仓库根下无 `skill/` 目录** |
| `frontend/` vs `frontend-v2/` | v1 经典静态页 vs v2 生产 SPA |
| 删除 MCP registry 条目 | 只取消 Hub 挂载与 workspace 同步；**不**卸载本机 npm 包 |

### 9.2 维护建议

- **改 task_type / Gate**：先改 `business/templates/templates.yaml`，再改 Skill。
- **改 Agent 能力边界**：`agents_registry.json` 的 `skills` / `mcp_servers` + UI 同步按钮。
- **改 UI**：只动 `frontend-v2/src/`；改 API 契约时同步 `backend/hub/api` 与 `frontend-v2/src/lib/api`。
- **大段历史文档**：在 `docs/`，与代码不一致时以 **代码与 `business/templates/`** 为准。

---

## 故障排查

| 现象 | 处理 |
|------|------|
| OpenCode CLI 未找到 | 安装 opencode 或设置 `OPENCODE_CLI_PATH` / `system_config.backends.opencode.cli_path` |
| `/v2` 空白 | `cd frontend-v2 && npm run build` |
| 看不到项目进度 | 确认 `business/tasks/state.db` 存在且 Hub 与 kernel 共用同一 `MYTEAM_ROOT` |
| MCP 不生效 | MCP 页启用 → Agent 勾选 → 「同步 MCP」→ 检查 workspace 内 `opencode.json` |
| Agent 私聊无 Skill 摘要 | 检查 `agents_registry.json` 的 `skills`；Skill 的 `description` 在 SKILL.md frontmatter |

---

**文档版本**：与仓库源码同步维护（2026-06-16）。若发现与代码不符，请以 `backend/`、`frontend-v2/src/`、`business/templates/` 为准并更新本 README。
