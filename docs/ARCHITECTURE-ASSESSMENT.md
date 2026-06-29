# myteam 项目工程架构全面评估报告

> 评估日期：2026-06-29
> 评估范围：系统架构 / 前后分离 / 后端架构 / 前端架构 / 工程与模块划分
> 评估依据：基于 `backend/`、`frontend/`、`business/`、`config/`、`scripts/`、`docs/` 全量源码与配置文件的实际核对，所有结论均附代码证据。

---

## 一、总体定位与架构骨架

myteam 是一个**轻量级多 Agent 协作平台**，定义了两条正交流：

```
A) Hub 交互流（人 ↔ Agent / 群）   — 流式
   浏览器 → hub/api/server.py → hub/services → base/agent_chat
        → adapter/registry → adapters/opencode|claude → AgentEvent → SSE

B) 编排内核流（goal → 多 Agent DAG 交付） — 批处理
   run_kernel.py → common/process.py（状态机）
        → common/agent_port.py（交互生命周期）
        → common/gate.py（确定性验收）
        → common/store.py（SQLite 真相库）
```

并明确划分**三层职责**（AGENTS.md / CLAUDE.md）：

| 层 | 路径 | 职责 |
|----|------|------|
| System Kernel | `backend/common/`、`backend/adapter/`、`backend/hub/` | Process / AgentPort / Gate / Store / contracts / Hub API / CLI 适配 |
| Strategy Registry | `business/templates/`、`business/config/`、`business/rules/`、`business/workflows/` | task_type / 角色 / 验收规则 / workflow |
| Skill / MCP Pack | `business/skills/*/SKILL.md`、`business/config/mcp_registry.json` | 单次执行方法论 / MCP 工具目录 |

**整体判断**：架构骨架**设计扎实、抽象清晰**，三层职责模型在配置层基本落地，但代码层存在若干泄漏与命名混淆。后端工程化程度明显高于前端。

---

## 二、后端架构评估

### 2.1 亮点 — 达到最佳实践的设计

#### ① 编排内核四层抽象干净分离

| 抽象 | 文件 | 职责 |
|------|------|------|
| Process 状态机 | `backend/common/process.py` | team_config → task_plan → wave 调度 → finalize |
| AgentPort | `backend/common/agent_port.py` | 交互投递 / 看门狗 / 幂等 / token 计量（506 行） |
| Gate 确定性验收 | `backend/common/gate.py`、`backend/common/plan_gate.py` | 契约 + 格式 + 完整性（D14/D15） |
| Store 真相库 | `backend/common/store.py` + `store_backend.py` + `store_sqlite.py` | 端口-适配器三层分离 |

子 pipeline 拆分清晰：`dag_dispatch.py`（纯函数 DAG 调度，无 I/O）、`decision_pipeline.py`（team_config/task_plan/triage 决策）、`task_pipeline.py`（execute 流水线 + Gate 重试）。

协作链路：`Process._dispatch` → 波次 `ready_tasks` → `TaskPipeline.run_task`（Gate 重试）→ 失败时 `DecisionPipeline.triage` → 拆分回 `PlanExpander.apply_split`。`process.py` L65-73 在 `__init__` 装配这三个 pipeline，是唯一的组合点。

#### ② Adapter 隔离彻底（核心不变量，落实到位）

- `backend/adapter/protocol.py`：`RunRequest` + `AgentEvent` 是仅有的两个跨 CLI 数据契约；`CLIAdapter` ABC + `AdapterCapabilities` 声明式能力。
- `adapters/opencode/parser.py` 与 `adapters/claude/parser.py` 是**唯一**知道 CLI 原生输出格式的地方（grep 确认 `part.text`/`sessionID` 仅出现在 parser 及其测试）。
- `backend/adapter/subprocess_cli.py`：进程组回收（SIGTERM→2s→SIGKILL）、cancel_event 旁路杀进程、stdout 流式 + stderr 汇总，子进程治理到位。
- 两个适配器都继承 `SubprocessCLIAdapter`，差异仅在命令行拼接和 parser。parser 隔离彻底：`adapters/opencode/parser.py` 是唯一知道 `part.text` / `sessionID` / `raw.get("type")` 等 opencode 原生字段的地方。

#### ③ Store 端口-适配器分离是教科书质量

- `store_backend.py`：`StoreBackend` Protocol（`@runtime_checkable`）+ `AbstractStoreBackend` ABC——仅声明 `connection` / `fts_enabled` / `close` 三个属性。文档明确"Swap SQLite for Postgres by implementing StoreBackend"。
- `store_sqlite.py`：`SQLiteStoreBackend`——每线程独立连接（`threading.local()`）+ WAL + `busy_timeout=5000` + FTS5 trigram 初始化 + memory_fts 回填。
- `store.py`：`Store` 领域门面——15 张表 ~60 个领域方法（project/task/interaction/run_event/memory/conversation/message/job/agent_runtime/workspace_event/deliverable/skill_review/agent_config）。

并发模型：每线程独立连接，WAL 共享；L2 真并行时 `ThreadPoolExecutor`（`process.py` L472）每个 worker 拿到独立连接。

#### ④ submit_result "拒绝而非抢救"契约校验严谨（D11/F1）

`backend/common/submit_result.py` 三道关：
1. 派发 token 校验（`MYTEAM_DISPATCH_TOKEN` 环境变量 == `interaction_id`）
2. `validate_response_dict` 契约校验（失败抛 `SubmitError` 不写文件）
3. `tempfile.mkstemp + os.fsync + os.replace` 原子写

契约路径已是唯一路径，旧 JSON 抢救与 `INTERACTION_CONTRACTS` 迁移开关已删除。

#### ⑤ AgentPort 看门狗与幂等治理

- 两段式看门狗（D7）：`soft_idle_sec=120`（疑似卡死，标记+告警）和 `hard_idle_sec=300`（取消+重试）。可按 `kind` 覆盖阈值（`idle_limits`）。
- 幂等/残留治理（D8）：派发前清旧文件；响应须 mtime 晚于请求 + `interaction_id` 匹配四条件全满足才采纳；`reconcile_on_start` 启动对账 GC 回收磁盘孤儿 `.response`。
- Token 计量：`_drain` 排空事件队列并提取 `step_finish` 的累计 token；兼容 cumulative/per-message 两种模式。
- 交付物保证：agent 写了文件但未 submit_result 时代为采纳（`_try_adopt_deliverable`）。
- 取消传播：`DeliveryContext.cancel_event` 供适配器订阅；`project_cancel.cancel_registry` 联动。
- 预算硬停：`budget_checker` 在交互进行中检测超预算 → cancel + `budget_exceeded`。

#### ⑥ Gate 确定性验收（D14/D15）

三类门禁（`gate.py`）：
1. 契约门禁 `check_contract` → 调 `contracts.validate_response_dict`
2. 格式/完整性门禁 `check_format`：防 stub（`is_stub`）、必需章节、标题层级、`file_exists`、可选 `must_include`
3. action 证据门禁 `check_action_evidence`：URL 合规 + 截图存在 + 可选实时核对标题（被反爬拦截不硬失败）

execute 串联：`check_execute` 按 `outcome_kind` 分流（artifact/action/code_project）。

`plan_gate.py`：`check_plan` 纯函数校验 task DAG（agent 存在性、task_type 注册、能力边界、依赖无悬空、无环 `topological_order` Kahn 算法、扇出上限）。

同一注册表源：down-link 的 `spec_for_task` 与 check-link 的 `resolve_format_spec` 共享 `registry.get_spec`——落实"down-link 与 check-link 共享一个 source"。

#### ⑦ 测试覆盖广

`backend/common/tests/` 有 **107 个测试文件**，含 e2e（`test_integration.py`、`test_platform_e2e_baseline.py`、`test_kernel_run.py`、`test_run_kernel.py`）、适配器测试（`test_opencode_parser.py`、`test_claude_parser.py`、`test_claude_adapter.py`）、契约测试（`test_contracts.py`、`test_api_contract.py`、`test_fe_hub_route_contract.py`）、Hub 测试（`test_observability_api.py`、`test_skills_api.py`、`test_projects_api.py`）。

### 2.2 后端架构问题

#### 【P0-1】kernel → hub/services 的逻辑环违反"内核不依赖 Hub"不变量

6 处 lazy import 构成逻辑环（均在函数体内，非 import-time，不致 ImportError，但构成逻辑环）：

- `backend/common/roundtable_runtime.py:154` → `hub.services.stream_fanout.fanout_stream_event`
- `backend/common/loop_discussion_runtime.py:123,161,269` → `hub.services.group_broadcast` / `stream_fanout` / `project_group_service`
- `backend/common/kernel_project_hooks.py:29` → `hub.services.project_group_service`
- `backend/common/adapter_mcp_registry.py:37,49` + `adapter_skill_registry.py:39,55,90` → `hub.services.agent_registry`

**影响**：`run_kernel.py` 单跑时这些 import 被 try/except 静默吞掉，导致圆桌/讨论 loop 的进度不可见。AGENTS.md 明示"kernel does not depend on the Hub"被实际代码违反。

**建议**：将这些回调统一收敛到 `ProjectHooks`（`process.py` L49 已存在该抽象，包含 `on_loop_round_done` / `on_team_ready` / `on_task_done` / `on_wave`）。Hub 启动时注入 hooks，kernel 单跑时 hooks=None。`adapter_{skill,mcp}_registry` 的 `list_available_agent_ids` 应改为从 `agents_registry.json` 直接读，不调 `hub.services.agent_registry`。

另外存在 base ↔ hub 双向依赖：`base/agent_chat.py` L18 import `hub.paths`；`hub/services/chat_service.py` L25 import `base.agent_chat`；`hub/api/routes/chat.py` L10 import `base.agent_chat`。

#### 【P0-2】`base/group_manager.py` 2554 行 god module

涵盖群组 CRUD + @mention 路由 + 圆桌调度 + 消息持久化 + 成员管理 + 排序 + 解散/恢复，与 `common/roundtable_runtime.py` 职责重叠。

**建议**：拆分为 `group_store.py`（CRUD + 持久化）、`group_mention.py`（@mention 路由）、`group_roundtable.py`（圆桌调度，与 `common/roundtable_runtime.py` 合并）。

#### 【P1-3】service 层零星 subprocess 违规

`backend/hub/services/chat_cancel.py:89` `kill_group_cli_processes` 直接 `subprocess.run(["pgrep",...])` + `os.kill(pid, SIGTERM)`。

**影响**：违反 AGENTS.md "service 层不得含 subprocess" 不变量。虽然这里是杀进程而非调 CLI，但 `pgrep/kill` 的进程匹配模式耦合了 workspace 路径约定，且 service 层出现 `subprocess` 会误导后续开发者认为可在此层调 CLI。

**建议**：将 `kill_group_cli_processes` 下沉到 `adapter/subprocess_cli.py`（已有 `terminate_process_group`），或通过 `AgentPort` 的 cancel 机制统一取消（`project_cancel.cancel_registry` 已有取消信号机制）。

#### 【P1-4】config 路由命名碰撞 + agents 端点分散

- `backend/hub/api/config_api.py`（560 行，Phase 4 配置：KB 模板/workflow profiles）与 `backend/hub/api/routes/config.py`（agent/backend/model 配置）都打 `tags=["config"]`。`server.py` L151 注册前者、`routes/__init__.py` L8 注册后者，两个 `config_router` 同名。
- `/api/agents` 端点散落 3 个文件：`routes/agents.py`（列表/详情/管理/notify/events/chats/registry）、`routes/config.py` L20（`/api/agents/{id}/config`）、`routes/system.py`。

**影响**：API 契约不一致，前端开发难以定位端点；维护时易漏改/重复实现。

**建议**：统一 config 路由命名（`config_api.py` → `phase4_config_api.py` 或加 prefix `/api/config/phase4`）；按资源聚合 agents 端点到单一 router。

#### 【P1-5】store/system_config.py 与 common/store.py 命名混淆 + base shim 残留

- `backend/store/system_config.py`：JSON 配置（port/default_backend/models/backends.cli_path），class `SystemConfig` + 单例 `system_config`。路径来自 `hub.paths.SYSTEM_CONFIG_FILE`。
- `backend/common/store.py`：SQLite 真相库，class `Store`。
- `backend/base/system_config.py`（12 行）：deprecated shim re-export `store.system_config`，但仍在 `base/agent_chat.py` L29、`hub/api/server.py` L41 等处被 import。

**影响**：新人极易把 `store.system_config`（配置）和 `common.store.Store`（真相库）混淆；`base/system_config.py` shim 增加一层间接，且 `store/` 目录名与 `common/store.py` 模块名碰撞。

**建议**：将 `store/system_config.py` 重命名为 `config/system_settings.py`，删除 `base/system_config.py` shim，全量替换 import 路径。

#### 其他发现

- **上帝模块（>1000 行）**：`base/group_manager.py` 2554 行、`common/store.py` 1322 行、`common/loop_runtime.py` 1167 行、`hub/api/config_api.py` 560 行、`common/agent_transport.py` 663 行、`common/task_pipeline.py` 542 行。
- **hub/services/tests/ 测试薄弱**：仅 1 个测试（`test_stream_fanout.py`）。
- **base/ 层** 2 个文件是 deprecated shim（`server.py`、`system_config.py`），1 个文件是疑似废弃入口（`server.py`）。

---

## 三、前端架构评估

### 3.1 技术栈

| 维度 | 实际值 | 评价 |
|------|--------|------|
| React | 19.2.6 | 最新 |
| Vite | 8.0.12 + @vitejs/plugin-react 6 | 最新 |
| React Router | 7.17.0 | 最新 |
| TypeScript | 6.0.2，`target: es2023`、`moduleResolution: bundler`、`verbatimModuleSyntax: true` | 严格 |
| Tailwind | 4.3.0 + @tailwindcss/vite（非 PostCSS 链路） | 现代 |
| UI | shadcn 风格（Radix + cva + clsx + tailwind-merge）14 个基础组件 | 一致 |
| 状态管理 | **无第三方库**（无 zustand/redux/jotai） | 轻量 |
| ESLint | flat config（js.recommended + typescript-eslint + react-hooks + react-refresh） | 有 |
| Prettier | **无** | 缺失 |
| 测试 | **完全无**（无 vitest/jest，无 `*.test.ts`） | 严重缺失 |

### 3.2 亮点

- **分层文档完整**：`frontend/ARCHITECTURE.md` 明确定义 `Pages → Sections → Components → Hooks → Ports → lib/api → Hub REST`，数据自上而下。
- **API 模块按 domain 拆分**：`lib/api/` 拆成 client/agents/chat/groups/projects/workflows/mcp/config，barrel 导出（`index.ts`）。
- **SSE 多模态**：`fetch + readStreamWithAbort`（chat）、`EventSource`（project/group）、`\n\n` framed（group）。
- **跨组件缓存失效**：`lib/dataRefresh.ts` 事件广播 + `DASHBOARD_DEPS` 级联失效，`useResourceQuery` 自动订阅重拉。
- **聊天流跨路由存活**：`agentChatStream.ts` 模块级单例 store，允许聊天在路由切换后不中断——是有意设计。

### 3.3 前端架构问题

#### 【P0-1】完全无前端测试

`frontend/` 下 0 个测试文件，`package.json` 无 `test` script。`agentChatStream.ts`（430 行状态机）和 `useResourceQuery` 这类核心逻辑零覆盖，回归风险高。`agentChatStream.ts` 含 busy/abortCtrl/activeTurn 等命令式状态机，在 React 之外可变——测试尤其重要。

#### 【P0-2】Ports 抽象是死代码 + 跨层调用普遍（最坏组合）

`lib/ports/` 定义了 `ChatPort`/`ProjectsPort` 接口 + `hubChatPort`/`hubProjectsPort` 默认实现，但**全仓 0 个外部消费者**（grep 确认只命中 ports 目录自身）。

同时 Components 普遍直接调 `lib/api/*`（30 处违规），典型如：

- `components/manage/AgentEditDialog.tsx` 直接 import 8 个 API 模块
- `components/project/ProjectTaskQualityCard.tsx` 直接调 `getTaskDetail`
- `components/workflow/WorkflowEditor.tsx` 直接调 `listAgents`、`listTaskTypes`、`listDeliveryTemplates`
- `components/project/ProjectDeliverablePanel.tsx` 直接调 `getDeliverableBundle`、`getDeliverableFile`
- `components/chat/AgentChatPanel.tsx` 直接调 `listBackends`、`listBackendModels`

既承担抽象维护成本，又没拿到抽象收益。**建议**：要么删 Ports、要么把 Component 的 API 调用上移到 Hooks 并通过 Port 注入。

此外，`useAgentChat` 不走 Port，直接 import `@/lib/agentChatStream`；`agentChatStream.ts` 直接 import `@/lib/api/chat`，绕过 `hubChatPort`。

#### 【P1-3】无路由懒加载，首屏 bundle 偏大

`App.tsx` 顶部 L2-12 同步 import 全部 9 个 Section + DashboardPage，全局 grep `React.lazy`/`Suspense` **0 命中**。`ManageSection.tsx`（1662 行）、`GroupsSection.tsx`（1177 行）全部进首包。**建议**：对 `/manage`、`/groups`、`/workflows`、`/skills`、`/mcp` 用 `React.lazy` + `<Suspense>` 拆分。

#### 【P1-4】类型未自动生成，FE/BE 易漂移

类型全部手写在 `lib/api/*.ts`（如 `projects.ts` 的 `ProjectSummary`、`TaskDetail`、`ProjectOverview`），后端是 Python Pydantic（`backend/common/contracts.py`），无 openapi-codegen/@hey-api/trpc。大量 `?` 可选字段把错误推迟到运行时（`undefined` 渲染）。`projects.ts` 的 `listProjects` 还在 API 层做 DTO 重映射（把后端 `title/workflow_label` 重映射为 `name/meta.workflow_label`），进一步拉大与后端原始 schema 距离。

**建议**：从 FastAPI 自动生成 OpenAPI，用 codegen 生成前端 types，或至少加一个契约快照测试。

#### 【P1-5】状态管理碎片化 + SSE 错误处理不一致

跨组件状态分散在三套机制：
1. `dataRefresh` 事件广播（Map + 订阅者模式）
2. `agentChatStream` 模块级可变单例（430 行，React 树外，含 sessions/busy/abortCtrl/activeTurn）
3. 各组件本地 useState

SSE 错误策略三套：
- `subscribeProjectStream` 直接 close 不重连（`projects.ts` L361）
- `connectAgentBackgroundEvents` 固定 3s 重连无退避（`agentChatStream.ts` L315）
- `sendAgentChat` 直接抛错不解析错误体

**建议**：统一 SSE 生命周期（重连退避 + 错误上报 + 取消语义），考虑把 `agentChatStream` 的可变单例收敛进一个可测试的 reducer。

#### 【P2-6】DiscordShell 包裹不一致

`App.tsx` L14-22 Dashboard 在路由层显式包 `<DiscordShell>`，其余 9 个路由在 Section 内部自包（grep 命中 9 个 Section 均自包）。布局职责归属不清。

#### 【P2-7】业务逻辑泄漏到 API 层

`groups.ts` L157,197,214 抛 `创建群组失败`/`更新成员顺序失败`，`workflows.ts` L352,369,391 抛 `创建分类失败`/`更新分类失败`/`移动 Skill 失败`。按 ARCHITECTURE.md L95「If it changes product behavior, it belongs in Hub」的口径，这些判定属业务规则泄漏。

#### 【P2-8】其他

- 无 Prettier，只有 ESLint，代码风格统一性依赖人工。
- `hubFetch` 无拦截器/auth/重试，扩展性差。
- 无 `components.json`（shadcn CLI 配置文件）——可能是手抄的 shadcn 组件。
- `src/lib/api.ts` 是 `@deprecated` 转发（`export * from "./api/index"`），遗留接口。

---

## 四、前后分离评估

### 4.1 分离质量

| 维度 | 评估 | 证据 |
|------|------|------|
| 物理分离 | ✅ 优 | `backend/` Python + `frontend/` React SPA，`frontend/dist` 由 Hub 静态托管于 `/v2/` |
| 接口契约 | ⚠️ 中 | REST + SSE，但无 OpenAPI schema 导出，类型靠人工对齐 |
| 错误信封 | ✅ 良 | `server.py` L172-189 统一 `APIError` + `HTTPException` 归一化，保留 `detail` 向后兼容 |
| CORS | ✅ | `MYTEAM_CORS_ORIGINS` 可配，默认 `*` |
| SPA fallback | ✅ | `server.py` L224-229 深链回退 `index.html` |
| 版本共存 | ✅ | 生产 `/v2/`，经典 UI `MYTEAM_V1_UI=1` 开放 `/classic` |

### 4.2 前后分离的核心问题

**契约同步靠人工**：后端 Pydantic 模型变更（如 `contracts.py` 的 `InteractionRequest`/`InteractionResponse`）无法在前端编译期感知，是前后分离架构最大的隐性风险。**建议**：从 FastAPI 自动生成 OpenAPI，用 codegen 生成前端 types，至少加一个契约快照测试（已有 `test_fe_hub_route_contract.py` 是好的起点）。

---

## 五、工程划分与模块边界评估

### 5.1 顶层划分

```
myteam/
├── backend/    全部 Python（common 内核 + hub Web + adapter CLI + base 兼容 + store JSON 配置 + memstack 记忆 + execution_harness 执行框架）
├── frontend/   生产 SPA（React 19）
├── business/   业务资产（templates/rules/skills/workflows/delivery_templates/playbooks/means/experience/hooks/agent-catalog/regression + config/workspaces/tasks 运行态）
├── config/     系统配置（system_config.json / skill_config.json，gitignore）
├── scripts/    运维与回归脚本（bootstrap/audit/test.sh/regression/）
└── docs/       设计文档
```

顶层划分**基本合理**：代码 / UI / 业务资产 / 运行态 / 运维 / 文档各归其位。

### 5.2 三层职责模型落地情况

**配置层 — 边界清晰**：

- `business/templates/templates.yaml` 是 task_type 权威单一来源（`registry.py` 注释明示"格式注册表——task_type 约束的单一出处"），`@lru_cache` 读取。每个 task_type 包含 `display_name` / `recommended_skills` / `deliverable_template` / `check_rules` / `outcome_kind`。
- `business/rules/` 的 universal/interactive/brainstorming/worker 由 `rules_merge.py` L39-87 按 profile 合并到临时文件 `/tmp/rules-{agent_id}-*.md`。
- `business/skills/` 每目录一个 SKILL.md（frontmatter: name/description/task_type），由 `common/skill/skill_catalog.py` 扫描，`catalog.yaml` 扁平索引。auto-* 前缀目录为草案（不可挂载），`_pending/` 为审批流。
- `business/workflows/` YAML 由 `workflow_loader.py` L105-140 加载 + `validate_workflow` 强制校验（agent 存在性、task_type 注册、DAG 合法、loop spec 合法）。
- Skill/MCP 挂载：`agents_registry.json` 的 `skills[]` → `agent_skills.py` `get_agent_skill_ids()` → `adapter_skill_registry.py` 批量 sync → workspace `.opencode/skills`。MCP 同理。Skill 挂载只读 registry，不看 task_type。

**代码层 — 3 处泄漏**：

#### 【泄漏 1】`business/hooks/` 是业务 Python 代码伪装成配置（高优先级）

`business/hooks/work_review_alignment.py` 是 150 行 Python（prompt 工程 + regex 匹配 + group message 发布 + artifact 保存），通过 `business_hook_loader.py` L16-34 的 `importlib.util.spec_from_file_location` 动态加载，缓存到 `_CACHE`。

注释"Kernel 不 import business 包"——用动态加载绕过分层约束，本质是内核扩展点却放在 `business/`。违反三层职责模型。

**建议**：在 `common/` 定义 hook 协议（抽象基类），`business/hooks/` 作为插件注册点；或将此逻辑内联为内核内置讨论策略。

#### 【泄漏 2】`backend/base/` 兼容层 shim 残留 + 与 hub/services 职责重叠（中优先级）

- `base/server.py`（5 行）废弃入口——"兼容入口 — 请使用 hub/api/server.py"
- `base/system_config.py`（12 行）deprecated shim re-export `store.system_config`
- `hub/paths.py` L1-7 也是"重新导出自 common.paths"的 shim
- `base/agent_chat.py` 既被 `hub/services/chat_service.py` 调用，又被 `hub/api/routes/chat.py` L10 直接 import 私有函数 `stream_chat`（跳过 services 层）

`base/` 6 个文件中 2 个是 shim，其余 4 个（agent_chat/agent_factory/agent_identity/group_manager）是被 hub/services 调用的共享逻辑。

**建议**：删除 `base/server.py`、`base/system_config.py` 两个 shim；将 `base/` 实质内容并入 `hub/services/` 或 `common/agent/`，消除 base 层。

#### 【泄漏 3】`backend/common/` 既放内核又放共享域（中优先级）

`common/` 同时包含内核（process/gate/agent_port/store/contracts/registry）+ 共享域（`skill/` 子包 9 个文件、`project_lib/`、`experience.py`、`delivery_templates.py`、`delivery_profiles.py`、`skill_extract.py`）。

**建议**：拆分为 `common/kernel/`（Process/Gate/AgentPort/contracts）+ `common/skill/`（已拆子包）+ `common/store/`（SQLite 层）+ `common/delivery/`（模板/profiles）。

### 5.3 配置 vs 运行态边界

`.gitignore` 处理清晰：
- **入库**：`business/templates/`、`business/rules/`、`business/skills/`、`business/workflows/`、`business/delivery_templates/`、`business/hooks/`、`backend/`、`frontend/src/`、`scripts/`、`docs/`
- **gitignore**（运行态）：`config/*.json`、`business/config/*`、`business/workspaces/`、`business/tasks/`（含 `state.db`）、`frontend/dist/`、`node_modules/`

**注意**：`config/USER.md` 入库（唯一例外，`.gitignore` 只忽略 `*.json`）。

### 5.4 已知 P0：22 个 task_type 未在 templates.yaml 注册

`docs/myteam-gap-assessment.html:573-581` 记录：`catalog.yaml` 定义了 22 个 task_type 的 Skill 路由（`code-writing`/`code-review`/`code-testing`/`system-design`/`architecture-review`/`prd`/`requirements`/`strategy`/`section-authoring`/`section-review`/`code-audit`/`test-plan`/`geo-plan`/`geo-audit`/`config-bundle`/`prompt-optimize`/`evaluation-rubric`/`workflow-design`/`office-doc`/`content`/`deck-build`/`diagram-build`），但 `templates.yaml` 缺对应 `check_rules` 定义。

违反 AGENTS.md 不变量"A new task_type must be added to templates.yaml first"。Gate（`registry.get_spec`）对这些 task_type 返回 None，无法验收规则校验。`scripts/audit_skill_matrix.py` 可检出但未阻断 CI。

**建议**：将 22 个 task_type 补入 `templates.yaml`，或将 `audit_skill_matrix.py` 加入 `scripts/test.sh` 作为 CI 门禁。

### 5.5 文档漂移

AGENTS.md / CLAUDE.md 反复引用 `docs/ARCHITECTURE.md`、`docs/FRAMEWORK-FREEZE.md`（或 `docs/FRAMEWORK_BOUNDARY.md`）、`docs/framework-decisions.md`（决策 D1–D19、F1 散落代码注释），但**这三个文件实际不存在**（glob 确认）。仅 `frontend/ARCHITECTURE.md` 存在。

决策编号（D7 看门狗、D8 幂等、D10 单内核、D11 统一交互契约、D12 串行核 L2 并行 DAG、D13 SQLite、D14 确定性 Gate、D15 成果形式、D18 失败语义、F1 拒绝抢救）在代码注释中作为唯一引用源，但缺少权威决策文档落盘——这是文档治理的显著缺口。

---

## 六、综合问题清单与改进优先级

| 优先级 | 类别 | 问题 | 影响范围 |
|--------|------|------|----------|
| **P0** | 前端 | 完全无前端测试，核心逻辑零覆盖 | 回归风险高 |
| **P0** | 工程划分 | 22 个 task_type 未在 templates.yaml 注册 | Gate 无法验收 |
| **P0** | 后端 | kernel → hub/services 逻辑环（6 处 lazy import） | 内核独立性受损 |
| **P1** | 前端 | Ports 死代码 + Components 跨层调 lib/api（30 处） | 分层名存实亡 |
| **P1** | 前端 | 无路由懒加载，首屏 bundle 偏大 | 性能 |
| **P1** | 前端 | 类型未自动生成，FE/BE 易漂移 | 契约一致性 |
| **P1** | 前端 | 状态管理碎片化 + SSE 错误处理三套 | 可维护性 |
| **P1** | 后端 | group_manager.py 2554 行 god module | 可维护性 |
| **P1** | 后端 | service 层 chat_cancel.py 用 subprocess | 违反不变量 |
| **P1** | 后端 | config 路由命名碰撞 + agents 端点分散 | API 一致性 |
| **P1** | 工程划分 | business/hooks/ 业务 Python 伪装配置 | 分层泄漏 |
| **P1** | 工程划分 | store/ vs common/store.py 命名混淆 + base shim 残留 | 新人困惑 |
| **P2** | 前端 | DiscordShell 包裹不一致（路由层 vs Section 层） | 一致性 |
| **P2** | 前端 | 业务逻辑泄漏到 API 层（错误判定） | 边界 |
| **P2** | 前端 | 无 Prettier，风格靠人工 | 风格统一 |
| **P2** | 工程划分 | common/ 既放内核又放共享域 | 模块边界 |
| **P2** | 文档 | ARCHITECTURE/FRAMEWORK-FREEZE/framework-decisions 引用但不存在 | 文档治理 |

---

## 七、总体结论

### 优势

1. **后端内核抽象达到行业最佳实践水平**：Process/AgentPort/Gate/Store 四层设计、端口-适配器 Store、submit_result 原子契约校验、确定性验收 Gate、adapter 隔离彻底——这些都是架构评审中的亮点。
2. **CLI 适配器隔离彻底**，新增 CLI 后端成本可控（只需 parser + adapter 实现，UI 不变）。
3. **三层职责模型（System/Strategy/Skill）在配置层落地清晰**：templates.yaml 单一来源、rules_merge 按 profile 合并、Skill 按目录组织。
4. **后端测试覆盖广**（107 文件），含 e2e、契约、适配器测试。
5. **前端技术栈全部最新**（React 19 + Vite 8 + RR 7 + TS 6 + Tailwind 4）。

### 短板

1. **前端工程化明显弱于后端**：零测试、零懒加载、零类型生成、Ports 死代码、跨层调用普遍——这是前后端质量最显著的断层。
2. **代码层有 3 处分层泄漏**：business/hooks 动态加载、base/ shim 残留、common/ 内核与共享域混合。
3. **kernel 独立性受损**：6 处 lazy import 构成逻辑环，"内核不依赖 Hub"不变量被绕过。
4. **文档治理缺口**：核心架构文档引用但不存在，决策编号散落代码注释无权威落盘。
5. **已知 P0 未闭环**：22 个 task_type 未注册 templates.yaml，`audit_skill_matrix.py` 检得出但未阻断 CI。

### 改进路径建议（不触动框架冻结区）

**短期（1-2 周）**：
- 补 22 个 task_type 到 `templates.yaml`
- 删 `base/server.py`、`base/system_config.py` 两个 shim
- `audit_skill_matrix.py` 加入 CI 门禁
- 前端加 vitest，对 `agentChatStream.ts` 和 `useResourceQuery` 写核心测试

**中期（1-2 月）**：
- kernel→hub 回调收敛到 `ProjectHooks` 注入
- 拆 `base/group_manager.py`
- 前端类型从 FastAPI OpenAPI 自动生成
- 删 Ports 抽象或真正应用（Component→Hook→Port 链路）
- `App.tsx` 改 `React.lazy` + `<Suspense>`

**长期（3-6 月）**：
- `common/` 拆 kernel/skill/store/delivery 子包
- `business/hooks` 改插件协议
- 补齐 `docs/ARCHITECTURE.md` 与 `docs/framework-decisions.md`
- 统一 SSE 生命周期管理
- `store/` 目录更名消除命名混淆

---

**文档版本**：与仓库源码同步维护（2026-06-29）。若发现与代码不符，请以 `backend/`、`frontend/src/`、`business/templates/` 为准并更新本报告。
