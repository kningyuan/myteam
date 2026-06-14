# myteam

轻量级 **多 Agent 协作平台**：一个 Web Hub（聊天 / Agent 管理 / 群组 / 可观测）+ 一个声明式编排内核（把一个目标 `goal` 自动拆成任务 DAG，按依赖 wave 调度多个 Agent 执行，支持可配置并行、确定性门禁校验、失败重试与 triage）。

Agent 执行统一通过 **opencode CLI** 适配器驱动（可扩展 claude 等其它 CLI）。

> 设计与决策细节见 [`docs/V1_CAPABILITY_PLAN.md`](docs/V1_CAPABILITY_PLAN.md)（v1 执行计划）、[`docs/framework-decisions.md`](docs/framework-decisions.md)（D1–D18）与 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

---

## 1. 架构概览（两条正交流程）

```
A) 聊天 / 群聊（人 ↔ Agent）
   Web UI → hub/api/server.py → hub/services/chat_service → base/agent_chat
          → adapters/opencode|claude → 统一 AgentEvent → SSE 推前端

B) 编排内核（目标 → 任务 DAG 自动执行）
   run_kernel.py → Process(状态机) + AgentPort + Store(SQLite)
     → team_config / task_plan（Main 决策）或 --workflow 固定 DAG
     → 按 wave 调度 execute：AgentPort → CLI 子进程
        → Agent 用 submit_result 写 workspace/.response/{interaction_id}.response
        → Gate 校验（契约 + 格式 + 完整性）→ 通过/重试/triage
     → Agent 协作靠 DAG + 交付物 + 上游摘要注入 prompt（非 Agent 互读 .trigger）
     → 可观测：Hub 只读同一 SQLite（/api/obs/...）
```

| 层 | 路径 | 职责 |
|----|------|------|
| API/UI | `backend/hub/api/`、`frontend/` | FastAPI 薄路由 + Web UI |
| 服务 | `backend/hub/services/`、`backend/base/` | 聊天/群组/项目编排 |
| 适配器 | `backend/adapter/`、`backend/adapters/opencode/` | CLI 协议归一为 `AgentEvent` |
| 存储 | `backend/store/` | 配置 JSON + 系统配置真相 |
| 编排内核 | `backend/common/` | `run_kernel / process / agent_port / gate / registry / store(SQLite)` |
| 可观测 | `backend/hub/api/observability_api.py` | 只读查询 + `run_event` SSE |

---

## 2. 依赖

| 依赖 | 说明 |
|------|------|
| Python 3.12 | 用 venv |
| Python 包 | `fastapi`、`uvicorn[standard]`、`pydantic>=2`、`PyYAML`（见 `requirements.txt`） |
| **opencode CLI** | **外部依赖，需单独安装并配置好模型 provider/鉴权**。默认查找 `~/.opencode/bin/opencode`；可用 `system_config.backends.opencode.cli_path` 或环境变量 `OPENCODE_CLI_PATH` 覆盖 |

内核实际调用形如：`opencode run --dangerously-skip-permissions --format json -m <model> --dir <workspace>`。模型 token/鉴权属于 opencode 自身配置，不在 myteam 内。

---

## 3. 新环境安装

```bash
# 1) 拉代码
git clone <repo> myteam && cd myteam

# 2) 安装并配置 opencode CLI（按 opencode 官方文档配置模型 provider），确认可用
opencode --version

# 3) Python 环境
python3.12 -m venv venv
venv/bin/pip install -r requirements.txt

# 4) 启动 Hub（首次会自动生成 config/system_config.json）
./run.sh start
#   打开 http://localhost:8765
```

> 系统配置 `config/*.json`、业务配置与运行态 `business/`（`business/config/*`、`business/workspaces/`、`business/tasks/state.db`）、`*.log` 均被 `.gitignore` 排除——它们是**每个环境自己的运行态/业务数据**，不入库，需在本机生成/配置。

---

## 4. 启动 / 入口

### 入口 A — Web Hub（UI + 聊天 + 可观测）

```bash
./run.sh start      # 监听 http://localhost:8765 (127.0.0.1:8765)
./run.sh stop       # 停止
```

`run.sh` 会自动定位 `venv/bin/python3`、设置 `PYTHONPATH=backend`、`MYTEAM_ROOT=仓库根`，缺依赖时自动 `pip install -r requirements.txt`，然后运行 `backend/hub/api/server.py`。

关键 API：`/api/agents`、`/api/backends`、`/api/groups`、`/api/projects`、`/api/obs/...`。

### 入口 B — 编排内核 CLI（跑一个项目）

```bash
export MYTEAM_ROOT="$PWD"
export PYTHONPATH="$PWD/backend"
export NO_PROXY="localhost,127.0.0.1,::1"

venv/bin/python3 backend/common/run_kernel.py <project_id> \
  --goal "你的项目目标..." \
  --mode one_shot \        # one_shot | recurring
  --budget 150000          # 可选：per-project token 硬上限
```

- 结果写入 SQLite（`business/tasks/state.db`），交付物写 `business/tasks/project/<project_id>/deliverables/`。
- 单次交互的契约响应写 `workspace-<agent>/.response/{interaction_id}.response`（请求快照在 `.trigger/{interaction_id}.request`）；详见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §4。
- 内核**不依赖 Hub 运行**（直连 opencode）；想在 UI 看进度就同时开着 Hub（读同一个库）。
- 退出码：`completed` → 0，否则非 0。

---

## 5. 配置

| 文件 / 目录 | 作用 | 来源 |
|------|------|------|
| **系统配置（随代码走，`config/`）** | | |
| `config/system_config.json` | 端口、默认 backend/model、`backends.opencode.cli_path`、模型列表 | 首次加载由 `store.system_config` 用默认值**自动生成** |
| `config/skill_config.json` | 协作/通知开关等系统级配置 | 运行时管理 |
| **业务配置（随业务领域走，`business/config/`，gitignore）** | | |
| `business/config/agents_config.json` | 每个 agent 的 `backend / model / workspace` | UI 建 agent 或手工写 |
| `business/config/agents_registry.json` | agent 注册表（Main 选团队时读） | 同上 |
| `business/config/groups.json`、`session_map.json`、`group_archives.json`、`chat_archives/` | 群组、会话映射、归档 | 运行时管理 |
| `business/config/.env` | 可选超时/重试覆盖（默认全注释 = 用默认值） | 已有模板 |
| `business/workspaces/workspace-<agent_id>/` | agent 工作目录（放 `AGENTS.md/IDENTITY.md/SOUL.md/MEMORY.md` 等人设与规则） | 建 agent 时生成 |

**Agent 名册模板**见 `business/templates/business-roster.json`（四条业务线、17 个角色：`main`、`deputy`、`product`、`arch`、`developer`、`frontend`、`tester`、`qa`、`test_dev`、`research`、`analyst`、`content`、`docs`、`seo`、`geo`、`social`、`ops`）。

首次或升级后合并到本机运行态：

```bash
python3 scripts/bootstrap_business_roster.py
```

写入 `business/config/agents_registry.json` 并创建缺失 workspace。  
调研专职 agent id 为 **`research`**（不是已废弃的 `researcher`）。`task_type=research` 也可派给具备该能力的 `product` / `arch` / `developer` 等。

默认模型由 `config/system_config.json` 与各 agent 的 `agents_config.json` 决定，非仓库硬编码。

### 团队协作框架的三层形态

myteam 的团队协作框架不是一个 Skill，而是系统级内核 + 可配置策略 + Skill 能力包：

| 层 | 路径 | 用途 |
|----|------|------|
| System Kernel | `backend/common/`、`backend/adapter/`、`backend/hub/api/observability_api.py` | Process / AgentPort / Gate / Store / Observability 等运行时机制 |
| Strategy Registry | `business/templates/templates.yaml`、`business/config/agents_registry.json`、`business/rules/` | task_type、角色名册、验收标准、证据规则、团队默认策略 |
| Skill Pack | `business/skills/*/SKILL.md`、`business/workspaces/*/AGENTS.md` | 具体执行能力、工具步骤、角色工作方法 |

经验法则：需要恢复、重试、审计、持久化的进系统；改变任务类型/验收标准/角色选择的进策略注册表；教 agent 怎么完成具体工作的做 Skill。

---

## 6. Workspaces 说明（是否都必须？）

**不是全都必须。**

- 每个 `business/workspaces/workspace-<agent_id>/` 对应一个 agent 的工作目录。**只有你实际会用到的 agent 才需要 workspace**。
- `main` 必备：负责 `team_config` / `task_plan` / `triage` 决策。其余 agent 只在被分配任务时才用到。
- 目录本身**按需自动创建**（框架会建 `.trigger` / `.response` 子目录，用于内核与 CLI 的交卷通道），缺目录不会让流程崩溃。
- 但一个完整 workspace 里的 `AGENTS.md`（opencode 跑 `--dir` 时自动读取）、`IDENTITY.md`、`SOUL.md`、`MEMORY.md` 等是该 agent 的**人设 / 规则 / 记忆**。**没有这些文件，agent 仍能执行，但没有人设与记忆，产出质量会下降**。
- 用不到的模板 workspace 可以删除。各 workspace 内残留的 `.openclaw` / `.sisyphus`（OpenClaw 时代产物）可手工清理。

> 经验法则：保留 `main` + 你实际编入团队的 agent，并确保它们的 workspace 里有 `AGENTS.md` 与身份文件。

---

## 7. 使用

- **对话 / 群聊**：开 Hub，在浏览器里与某 agent 聊天，或在群里 `@agent`（走聊天层 A）。
- **跑项目（自动编排）**：用入口 B 给一个 `goal`，Main 自动配团队 + 规划 DAG，各 agent 用 `submit_result` 交付，框架 Gate 校验、必要时重试 / triage（走编排层 B）。
- **看进度 / 成本**：Hub 的 `/api/obs/...`（项目总览 / 时间线 / 成本 + SSE）或 `/api/projects`。

### 冒烟示例

```bash
export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend" NO_PROXY="localhost,127.0.0.1,::1"
venv/bin/python3 backend/common/run_kernel.py smoke_test \
  --goal "为 example.com 做一次 GEO 快速评估" --budget 80000
```

输出 `status: completed` 即环境就绪。

---

## 8. 测试

```bash
PYTHONPATH="$PWD/backend" venv/bin/python3 -m pytest backend -q
```

用例数随分支演进；发版前跑全量 `backend`。

---

## 9. 目录结构

```
myteam/
├── run.sh                       # Hub 启停脚本
├── requirements.txt
├── backend/                     # 系统功能（唯一一棵后端树）
│   ├── hub/api/server.py        # FastAPI 入口（端口 8765）
│   ├── hub/api/observability_api.py
│   ├── hub/services/            # 聊天/群组/项目服务
│   ├── base/                    # 领域逻辑（agent_chat / factory / groups）
│   ├── adapter/ + adapters/opencode/   # CLI 适配抽象 + opencode 实例
│   ├── store/                   # 配置/系统配置（JSON 真相）
│   └── common/                  # 编排内核：run_kernel / process / agent_port / gate / registry / store(SQLite)
├── frontend/                    # Web UI
├── config/                      # 系统配置（system_config / skill_config，随代码走）
├── business/                    # 业务领域（gitignore 运行态）
│   ├── skills/publish-post/     # Skill 能力包：具体动作/领域执行方法
│   ├── templates/templates.yaml # Strategy Registry：task_type 格式/验收/证据规则
│   ├── rules/                   # Strategy / Agent Rules：团队通用约束
│   ├── config/                  # 业务配置 + 运行态（agents_config / groups / session_map / .env ...）
│   ├── workspaces/              # 各 agent 工作目录
│   └── tasks/                   # 运行态：state.db、project/<id>/deliverables
└── docs/                        # 见 docs/README.md（ARCHITECTURE / 0608 升级 / new 需求）
```

---

## 10. 故障排查

- **`OpenCode CLI 未找到`**：装好 opencode；或设 `config/system_config.json` 的 `backends.opencode.cli_path`，或 `export OPENCODE_CLI_PATH=/abs/path/opencode`。
- **`team_config / task_plan 失败`**：检查 `main` 的 workspace 与模型可用性；弱模型可能产不出合法契约，内核已在提示词里注入具体 JSON 骨架 + 可用 agent/task_type 白名单。
- **端口被占**：`./run.sh stop` 或改 `LOCAL_AGENT_PORT`。
- **看不到进度**：内核写 `business/tasks/state.db`，需用入口 A 的 Hub 读取同库展示。
