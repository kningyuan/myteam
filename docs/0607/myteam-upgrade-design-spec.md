# myteam 系统升级设计实现规格书

> **文档类型**：设计实现规格（Design & Implementation Specification）  
> **版本**：v1.2  
> **基干**：[myteam-upgrade-comprehensive-plan.md](./myteam-upgrade-comprehensive-plan.md)（下文称"产品规格"）  
> **覆盖阶段**：R0–R4  
> **受众**：
>   - **Product Agent**：通过 §5 追溯矩阵确认设计覆盖产品需求
>   - **Developer Agent**：按 §4 分阶段规格实现
>   - **Test Agent**：按 §6 测试规格编写用例

---

## 目录

1. [文档目的与阅读指南](#1-文档目的与阅读指南)
2. [架构总览与模块地图](#2-架构总览与模块地图)
3. [核心数据流设计](#3-核心数据流设计)
4. [分阶段设计实现规格](#4-分阶段设计实现规格)
   - 4.1 R0 — 工程可信底座
   - 4.2 R1 — 产品闭环（CLI + Hub 基础）
   - 4.3 R2 — Agent Workspace 一体化
   - 4.4 R3 — 体验与可视化升级
   - 4.5 R4 — 资源层与对外能力
5. [需求-设计-实现追溯矩阵](#5-需求-设计-实现追溯矩阵)
6. [测试规格](#6-测试规格)

---

## 1. 文档目的与阅读指南

### 1.1 文档定位

产品规格描述"做什么"和"长什么样"；本文档描述"怎么设计"和"怎么实现"。

```
产品规格（Comprehensive Plan）── 做什么、验收什么
       │
       ▼
本文档 ── 设计成什么样、改哪些模块、接口契约、数据迁移
       │
       ▼
实现代码 ── 最终产出的文件变更
```

### 1.2 各角色阅读路径

| 角色 | 阅读重点 |
|------|----------|
| **Product Agent** | §2（架构是否合理）+ §5（追溯矩阵确保全覆盖）→ 判断设计与产品需求一致 |
| **Developer Agent** | §4（分阶段实现规格，含接口契约和模块职责）→ 编码实现 |
| **Test Agent** | §6（测试规格）+ §5（追溯矩阵）→ 编写覆盖所有需求的测试用例 |
| **Main Agent** | §3（数据流）+ §4 阶段门禁 → 编排验收 |

### 1.3 冲突裁决

`CLAUDE.md` invariant > `framework-decisions.md` > 产品规格 > 本文档。

---

## 2. 架构总览与模块地图

### 2.1 架构分层（物理模块边界）

```
┌──────────────────────────────────────────────────────────────────┐
│  FRONTEND (frontend/)                                            │
│  ├── index.html        SPA HTML shell + 所有模态框               │
│  ├── app.js            SPA 主逻辑 (3488行, R3-7需拆分)           │
│  ├── style.css         样式表 (1531行, R3-7需拆分)               │
│  ├── markdown.js       Markdown 渲染                             │
│  └── check.js          校验辅助                                  │
├──────────────────────────────────────────────────────────────────┤
│  HUB API (backend/hub/)                                          │
│  ├── api/server.py           FastAPI 主应用 + 全部路由 (829行)    │
│  ├── api/observability_api.py 可观测路由                         │
│  ├── services/chat_service.py     聊天服务                       │
│  ├── services/agent_registry.py    Agent 注册表                  │
│  ├── services/agent_broadcast.py    SSE 广播                     │
│  ├── services/group_broadcast.py    群组 SSE 广播                │
│  ├── services/notify_service.py     通知服务                     │
│  ├── services/project_service.py    项目服务                     │
│  ├── services/project_group_service.py 项目-群组绑定              │
│  └── services/channel_service.py     频道服务                     │
├──────────────────────────────────────────────────────────────────┤
│  ORCHESTRATION KERNEL (backend/common/)                          │
│  ├── run_kernel.py        入口 (303行)                            │
│  ├── process.py           核心状态机 (282行)                      │
│  ├── store.py             SQLite 存储 (748行)                     │
│  ├── agent_port.py        Agent 端口 (350行)                      │
│  ├── agent_transport.py   Agent 传输层 (277行)                    │
│  ├── gate.py              执行门禁 (233行)                        │
│  ├── plan_gate.py         计划门禁 (109行)                        │
│  ├── contracts.py         契约定义 (266行)                        │
│  ├── registry.py          注册表 (118行)                          │
│  ├── dag_dispatch.py      DAG 调度 (46行)                         │
│  ├── task_pipeline.py     任务管道 (231行)                        │
│  ├── decision_pipeline.py 决策管道 (143行)                        │
│  ├── plan_expansion.py    计划展开 (41行)                         │
│  ├── plan_splice.py       计划拼接 (40行)                         │
│  ├── project_admin.py     项目管理 (40行)                         │
│  ├── workspace_gc.py      Workspace GC (145行)                    │
│  ├── audit_log.py         审计日志                                │
│  ├── agent_bootstrap.py   Agent 初始化                            │
│  ├── submit_result.py     结果提交流程                            │
│  ├── paths.py             路径常量 (139行)                        │
│  ├── config.py            配置                                    │
│  └── logger.py            日志                                    │
├──────────────────────────────────────────────────────────────────┤
│  ADAPTER (backend/adapter/ + backend/adapters/)                  │
│  ├── adapter/events.py        统一事件模型                       │
│  ├── adapter/protocol.py      Adapter 协议                        │
│  ├── adapter/registry.py      注册表                              │
│  ├── adapter/sse.py           SSE 编码                            │
│  ├── adapters/opencode/parser.py   OpenCode 解析                  │
│  ├── adapters/opencode/adapter.py   OpenCode 适配                 │
│  ├── adapters/claude/parser.py     Claude Code 解析               │
│  └── adapters/claude/adapter.py     Claude Code 适配              │
├──────────────────────────────────────────────────────────────────┤
│  BUSINESS CONFIG & RUNTIME (business/)                           │
│  ├── config/agents_config.json     Agent 配置                     │
│  ├── config/agents_registry.json   Agent 注册表                   │
│  ├── templates/templates.yaml      任务模板                       │
│  ├── tasks/state.db                SQLite 运行时                  │
│  ├── tasks/project/{id}/deliverables/ 交付物                     │
│  ├── workspaces/workspace-{id}/    工作空间                       │
│  ├── skills/                        技能包                        │
│  └── rules/                         规则                          │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 新增/修改模块清单

| 阶段 | 新文件 | 修改文件 |
|------|--------|----------|
| R0 | — | `backend/common/tests/*`, `backend/hub/api/server.py` |
| R1 | `business/demo/` 目录 | `backend/common/run_kernel.py`, `backend/hub/api/server.py`, `backend/hub/services/project_service.py`, `frontend/app.js`, `frontend/index.html` |
| R2 | `backend/common/workspace_events.py`, `backend/common/job_supervisor.py`, `backend/common/event_handler.py` | `backend/common/store.py`, `backend/hub/api/server.py`, `backend/hub/api/observability_api.py`, `backend/hub/services/channel_service.py` |
| R3 | `frontend/dag-renderer.js`, `frontend/timeline.js`, `frontend/cost-chart.js` | `frontend/app.js`, `frontend/style.css`, `frontend/index.html` |
| R4 | `backend/hub/api/resource_api.py`, `backend/common/resource_index.py` | `backend/hub/api/server.py` |

---

## 3. 核心数据流设计

### 3.1 项目创建与执行

```
[用户] → POST /api/projects (goal, mode, budget)
  → server.py: api_create_project()
    → project_service.py: create_project() → store.upsert_project()
    → channel_service.py: create_channel("channel/project-{id}")
    → WorkspaceEvent(PROJECT_CREATED)  ← Hub 直接写
    → 返回 {project_id}
  → POST /api/projects/{id}/run
    → job_supervisor.py (R2): Supervisor.start_job()
      → Store jobs 表写入 (status=running, pid=...)
      → 启动 run_kernel subprocess
        → process.py: Process.run()
          → Store task 表展开 DAG
          → dag_dispatch.py: 调度就绪 node
          → agent_port.py: 执行交互
            → agent_transport.py → adapter → CLI subprocess
          → gate.py: 校验输出
          → Store task 更新
          → Store run_event 追加（kernel 的唯一写入点）
      → [kernel subprocess 独立运行，通过 SQLite 共享状态]

  ← Supervisor/ProjectionRunner（Hub 进程内）轮询 Store.run_event
    → 读取未投影的 run_event 行
    → 通过 interaction_id → task 表 → project_id 反查归属
    → 转换为 WorkspaceEvent 写入 workspace_event 表
    → SSE 广播 → 前端实时更新
```

**关键约束**：`run_kernel` 是独立 subprocess，不直接写 `workspace_event` 表。Kernel 只写 `run_event` + `task`/`interaction` 表。Hub 侧通过 **ProjectionRunner 轮询** 将 run_event 投影为 WorkspaceEvent。

### 3.2 事件处理链（R2）

```
Kernel subprocess 状态变更
  → Store run_event 追加（kernel 内部，不感知 Hub）
  → ─ ─ ─ ─ ─ ─ [进程边界] ─ ─ ─ ─ ─ ─
  → Hub 侧 ProjectionRunner（轮询，默认 2s 间隔）
    → list_run_events(last_seq) 读取新行
    → 按 run_event.kind 映射为 WorkspaceEvent.type
    → 通过 interaction_id → task 反查 project_id
    → append_workspace_event() 持久化
    → EventPipeline.dispatch(workspace_event)
      → sse_notification_handler → SSE 广播到前端
      → channel_projection_handler → 写入项目频道
      → audit_log_handler → 审计日志
```

**主路径**：轮询（2s 间隔），非回调。原因是 kernel subprocess 无法同步回调 Hub 进程。

**兜底**：Hub 启动时全量扫描未投影 run_event。定时器 `_poll_interval=2s` 可配置。

### 3.3 取消流程

```
[用户] → POST /api/projects/{id}/cancel
  → job_supervisor.py: Supervisor.cancel_job()
    → Store jobs.cancel_requested = true
    → SIGTERM → Process 检测 → 安全终止
    → Store 标记 cancelled
    → WorkspaceEvent(cancel)
    → SSE 推送 → 前端更新
```

### 3.4 交付物读取

```
[用户] → GET /api/obs/projects/{id}/deliverables
  → observability.py: get_project_deliverables()
    → Store 查询 task 列表
    → 聚合 deliverables 目录文件树
  → 前端渲染文件树
  → [用户点击文件] → GET /api/obs/projects/{id}/deliverables/{path}
    → 读取文件内容 + MIME
    → 前端预览面板渲染 (Markdown/文本/下载)
```

---

## 4. 分阶段设计实现规格

### 4.1 R0 — 工程可信底座

#### R0-1 修复测试回归

**设计决策**：SSE 测试超时是因为 `test_observability_api.py` 中的 SSE endpoint 测试等待真实事件流 >120s 未终结。修复方案：mock 终态事件或加 timeout。

**涉及模块**：
- `backend/common/tests/test_observability_api.py`
- `backend/hub/tests/`（目录确认是否存在）

**接口变更**：无

**实现规格**：

```python
# test_observability_api.py — SSE 测试 timeout 修复
# 问题：SSE endpoint 流不终结，httpx 等待直到默认超时
# 修复策略（二选一）：
#   策略A：加 timeout 参数，使用 anyio 取消
#   策略B：mock AgentEvent 流，测试不依赖真实 SSE
# 推荐策略A，保持集成测试真实性

# 示例改动：
# @pytest.mark.timeout(30)  # 30s 超时
# async with client.stream("GET", url) as resp:
#     async for line in resp.aiter_lines():
#         if "done" in line: break

# 验收条件：
# 1. PYTHONPATH=backend venv/bin/python3 -m pytest backend -q
# 2. 全量通过，无 >30s 的测试
# 3. 总耗时 <60s
```

#### R0-2 修复交付物 API

**设计决策**：`test_deliverable_read` 和 `test_deliverable_file_read` 失败原因是 `get_task_deliverable_bundle` 返回路径与实际 API 路由不一致。需要对 store.py 中的 `bundle` 方法与 API handler 做对齐。

**涉及模块**：
- `backend/common/store.py`：检查 `get_task_deliverable_bundle` 逻辑
- `backend/hub/api/server.py`：deliverable 路由对齐
- `backend/common/tests/test_project_artifacts.py`

**接口变更**：无（修复回归，不改接口）

**验收条件**：
1. 前述 2 例通过
2. Hub 可读取 demo 项目 deliverable

#### R0-3 引入 CI

**设计决策**：在 `scripts/test.sh` 中定义本地 CI 脚本，GitHub Actions 配 `.github/workflows/test.yml`。

**涉及模块**：
- 新建 `scripts/test.sh`
- 新建 `.github/workflows/test.yml`

**验收条件**：
1. `scripts/test.sh` 可一键执行
2. 文档写入 `CLAUDE.md`

#### R0-4 FastAPI lifespan 迁移

**设计决策**：`@app.on_event("startup")` → `FastAPI(lifespan=lifespan_ctx)`。将 `_startup_resume_projects()` 和 `gc_workspace()` 移入 lifespan 上下文管理器。

**涉及模块**：
- `backend/hub/api/server.py`：替换 `@app.on_event`

**接口变更**：
```python
# 旧
@app.on_event("startup")
async def _startup_resume_projects():
    ...

# 新
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    await _startup_resume_projects()
    yield
    # shutdown (如需要)
```

**验收条件**：
1. 启动无 DeprecationWarning
2. auto-resume 行为不变

---

### 4.2 R1 — 产品闭环（CLI + Hub 基础）

#### R1-1 Demo 目录化

**设计决策**：将 Demo 从 `run_kernel.py` 内的 `_DEMO_GOAL` 字符串常量，抽取为 `business/demo/` 目录，包含可编辑的 goal 和 agent 配置。

**涉及模块**：
- 新建 `business/demo/` 目录
- 修改 `backend/common/run_kernel.py`

**数据契约**：

```
business/demo/
├── README.md                 # Demo 说明
├── goal.txt                  # Demo goal（与现有 _DEMO_GOAL 内容一致）
├── agents_config.json        # Demo 用 agents_config（子集）
└── templates.yaml            # Demo 用 templates（可选覆盖）
```

**goal.txt** 格式：
```
第一行为 goal 文本，后续行为空或注释（以 # 开头）。
```

**接口变更**：
```python
# run_kernel.py
# 新增 --demo-dir 参数
# 默认: business/demo/
# --demo 时:
#   1. 读取 demo_dir/goal.txt → goal
#   2. 读取 demo_dir/agents_config.json（可选覆盖）
#   3. 如果指定了 --project-id，用该 id；否则自动生成 demo-{timestamp}
```

**验收条件**：
1. 全新 checkout：`--init` → `--demo` <5min exit 0
2. deliverable 存在
3. 与 project_id 互斥

#### R1-2 CLI 友好错误与进度

**设计决策**：在 `process.py` 的异常处理链中增加结构化错误映射。在 `run_kernel.py` 中添加进度条（非 verbose 模式）。

**涉及模块**：
- `backend/common/process.py`：异常 → 用户消息映射
- `backend/common/run_kernel.py`：进度条输出
- `backend/common/notify_format.py`（已有 `format_error` 等）

**接口变更**：

```python
# process.py — 新增 ErrorFormatter
ERROR_MAP = {
    FileNotFoundError: {
        "agent_workspace": lambda e, agent_id: {
            "code": "WORKSPACE_NOT_FOUND",
            "message": f"找不到 agent「{agent_id}」的工作空间",
            "hint": "请确认 workspace 目录存在或执行 --init",
        },
        "config": lambda e, path: {
            "code": "CONFIG_NOT_FOUND",
            "message": f"缺少配置文件 {path}",
            "hint": "可执行 --init 生成默认配置",
        },
    },
    RuntimeError: {
        "task_plan_out_of_bounds": lambda e, agent: {
            "code": "PLAN_OUT_OF_BOUNDS",
            "message": f"编排规划失败：main 分配了名册外的 agent「{agent}」",
            "hint": "需检查 agents_registry.json",
        },
    },
    subprocess.CalledProcessError: lambda e: {
        "code": "CLI_EXECUTION_FAILED",
        "message": f"CLI 后端执行失败（exit code {e.returncode}）",
        "hint": "请确认 CLI 安装正确且已登录",
    },
}

# run_kernel.py — 进度条
# 非 verbose 模式：
# [1/5] 🔍 researching    |████████░░|  80%  4123 tokens
# [2/5] 📝 strategizing   |████░░░░░░|  40%  1200 tokens
```

**验收条件**：
1. 5 类常见错误无 Python 堆栈
2. 完成时有 task 列表摘要
3. 错误写入 `run_event` 可查询

#### R1-3 Hub 内创建并启动项目

**设计决策**：这是 R1 核心。在 Hub 中实现完整的"创建项目→启动运行"流程。R1 用线程启动 job（R2-3 再升级为 Supervisor）。`jobs` 表 schema 需与 R2-3 兼容。

**涉及模块**：
- `backend/hub/api/server.py`：新增 `POST /api/init`、`POST /api/demo`、修改 `POST /api/projects`、`POST /api/projects/{id}/run`
- `backend/hub/services/project_service.py`：新增/修改 `create_project`、`run_project`
- `backend/common/job_supervisor.py`（R1 最小实现，R2-3 扩展）
- `frontend/app.js`：Home 空态 + 新建项目模态框 + 启动流程
- `frontend/index.html`：Home 空态模板、创建项目模态框

**API 契约**：

```python
# POST /api/projects
# Request:
{
    "goal": str,           # 必填
    "title": str | None,   # 可选，默认 = goal[:50]
    "mode": "one_shot" | "recurring",  # 默认 one_shot
    "budget": int | None,  # 默认 None（不限）
    "backend": str | None, # 默认 None（system_config.default_backend）
    "project_id": str | None,  # 可选，自动生成 ui_{slug}_{ts}
}
# Response 200:
{
    "project_id": str,
    "title": str,
    "created": True,
}

# POST /api/projects/{id}/run
# Request: {}
# Response 200:
{
    "project_id": str,
    "started": True,
}

# POST /api/init
# Request: {}
# Response 200:
{
    "success": True,
    "message": "已初始化所有 Agent 工作空间",
}

# POST /api/demo
# Request: {}
# Response 200:
{
    "project_id": str,
    "started": True,
}
```

**数据模型变更**：

```python
# store.py — jobs 表（R1 最小 schema，R2-3 扩展）
_jobs_SCHEMA = """
CREATE TABLE IF NOT EXISTS job (
    job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    pid INTEGER,
    started_at TEXT,
    updated_at TEXT,
    cancel_requested INTEGER DEFAULT 0,
    error TEXT,
    FOREIGN KEY (project_id) REFERENCES project(project_id)
);
"""
```

**前端实现规格**：

```html
<!-- index.html — Home 空态（新增 #home-empty-state） -->
<div id="home-empty-state" class="empty-state">
  <div class="empty-illustration">🎯</div>
  <h2>欢迎使用 myteam Agent Team Workspace</h2>
  <p>编排、协作、交付 — 一切尽在浏览器</p>
  <div class="empty-actions">
    <button onclick="S.api.init()" class="btn btn-primary">初始化 Agent</button>
    <button onclick="S.api.runDemo()" class="btn btn-secondary">运行 Demo</button>
    <button onclick="S.ui.showNewProjectModal()" class="btn btn-outline">创建项目</button>
  </div>
</div>

<!-- index.html — 新建项目模态框（已有 #new-project-modal，需增强） -->
```

```javascript
// app.js — 新增 API
S.api = {
  init: async () => {
    const res = await fetch('/api/init', {method:'POST'});
    const data = await res.json();
    S.ui.showToast(data.message || '初始化完成');
    S.ui.refreshHome();
  },
  runDemo: async () => {
    const res = await fetch('/api/demo', {method:'POST'});
    const data = await res.json();
    S.ui.showToast('Demo 已启动');
    S.ui.navigateToProject(data.project_id);
  },
}

// app.js — 修改 createProject
// 现有 #new-project-modal 有 np-goal/np-mode/np-budget/np-title
// 需增强：提交后调用 POST /api/projects → POST /api/projects/{id}/run
```

**R1 实现约束**：
- `jobs` 表 schema 固定，**禁止 R2-3 重写表结构**（仅可扩展字段和 Supervisor 逻辑）
- `_KERNEL_RUNS` 内存 dict **保留**，R2-3 才替换为 Supervisor
- 线程启动 job：`threading.Thread(target=run_kernel.run_project, ...)`

**验收条件**：
1. 不打开终端即可完成 demo
2. 不打开终端即可创建并启动自定义项目
3. Home 空态三按钮可见可用

#### R1-4 交付物闭环

**设计决策**：修复现有 deliverable API 使其稳定，同时前端实现文件树 + 预览面板。

**涉及模块**：
- `backend/common/store.py`：修复 `get_task_deliverable_bundle`
- `backend/hub/api/server.py`：对齐路由
- `backend/common/observability.py`：聚合 `get_project_deliverables`
- `backend/common/project_artifacts.py`：读取交付物
- `frontend/app.js`：交付物文件树 + 预览面板

**API 契约**：

```python
# GET /api/obs/projects/{id}/deliverables
# Response 200:
{
    "project_id": str,
    "tasks": {
        "t_1": {
            "task_id": "t_1",
            "name": "调研",
            "agent": "researcher",
            "status": "completed",
            "deliverables": [
                {"path": "report.md", "size": 1234, "mime": "text/markdown"},
                {"path": "data.csv", "size": 5678, "mime": "text/csv"},
            ]
        },
        ...
    }
}

# GET /api/obs/projects/{id}/deliverables/{path}
# Response 200: 文件内容 + Content-Type header
# Response 404: {"error": {"code": "DELIVERABLE_NOT_FOUND", ...}}
```

**前端实现规格**：

```javascript
// app.js — 交付物 tab 渲染
// 左侧文件树：按 task 分组，每项为可点击的文件名
// 右侧预览面板：Markdown 渲染 / 纯文本 / 下载按钮

// deliverable 点击事件委托
// 1. 点击文件 → GET deliverables/.../{path}
// 2. 判断 MIME → text/markdown → markdown.js 渲染
// 3. 其他文本 → <pre> 展示
// 4. 非文本 → 提示下载
```

**Deliverables 页完整 UI 规格**（产品规格 §5.2 终态）：

```
┌─────────────────────────────────────────────────────┐
│  交付物                          [project: 调研报告] │
│  ┌──────────────┬──────────────────────────────────┐│
│  │ 📁 t_1 调研   │  ┌─ 报告预览 ──────────────────┐ ││
│  │   ├ report.md │  │                              │ ││
│  │   └ data.csv  │  │  # AI 编码工具调研报告       │ ││
│  │ 📁 t_2 策略   │  │                              │ ││
│  │   └ plan.md   │  │ ## 1. 工具对比               │ ││
│  │               │  │ Cursor: ...                  │ ││
│  │               │  │ Claude Code: ...             │ ││
│  │               │  │                              │ ││
│  │               │  └──────────────────────────────┘ ││
│  │               │  下载⬇  标记最终✅  版本对比📋   ││
│  └──────────────┴──────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

**交互规格**：
1. 文件树按 task 分组，task 名称可点击展开/折叠
2. 点击文件 → 右侧预览。支持：Markdown 渲染（`markdown.js`）、纯文本（`<pre>`）、图片（`<img>`）
3. 下载按钮 → 触发下载，使用原始文件名
4. **标记最终交付** → `POST /api/projects/{id}/deliverables/{path}/mark-final` → 文件标记为最终版本。标记后显示 ✅ 徽章。再次点击取消标记。
5. **版本对比** → 同一文件路径有多次写入时，右侧面板底部显示版本 tab（v1/v2/v3...），点击切换
6. 项目级聚合列表 → 在最上方显示所有已标记最终的文件快速入口

**终态交付物 API 扩展**：

```python
# POST /api/projects/{id}/deliverables/{path}/mark-final
# Request: {"final": True | False}
# Response 200:
{
    "path": "report.md",
    "marked_final": True,
    "version": 2,
}

# GET /api/obs/projects/{id}/deliverables — 响应增强
# 新增字段 per deliverable:
{
    "path": "report.md",
    "size": 1234,
    "mime": "text/markdown",
    "is_final": True,          # 是否标记最终
    "version": 2,               # 当前版本号
    "versions": [               # 版本历史
        {"version": 1, "size": 1000, "created_at": "..."},
        {"version": 2, "size": 1234, "created_at": "..."},
    ],
}
```

**数据模型变更**：

```sql
-- store.py — deliverable 版本跟踪
-- 存储在 task 的 meta 字段中，结构：
{
    "deliverables": {
        "report.md": {
            "versions": [
                {"version": 1, "size": 1000, "created_at": "..."},
                {"version": 2, "size": 1234, "created_at": "..."},
            ],
            "is_final": True,
        }
    }
}
```

**验收条件**：
1. demo 跑完后在 Hub 预览主报告
2. 下载文件内容与磁盘一致
3. Markdown 文件渲染为格式化文本
4. 可标记/取消标记最终交付

#### R1-5 Hub/API 友好错误

**设计决策**：统一 API 错误格式为 `{error: {code, message, hint, doc_url}}`。添加 FastAPI exception handler 拦截已知异常。

**涉及模块**：
- `backend/hub/api/server.py`：添加 exception handlers

**接口变更**：

```python
# server.py — 统一错误处理
class APIError(Exception):
    def __init__(self, code: str, message: str, hint: str = "", doc_url: str = "", status_code: int = 400):
        self.code = code
        self.message = message
        self.hint = hint
        self.doc_url = doc_url
        self.status_code = status_code

@app.exception_handler(APIError)
async def api_error_handler(request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "hint": exc.hint,
                "doc_url": exc.doc_url,
            }
        },
    )

# 错误码一览
ERROR_CODES = {
    "WORKSPACE_NOT_FOUND":     (404, "找不到 agent 工作空间", "执行 --init"),
    "CONFIG_NOT_FOUND":        (404, "缺少配置文件", "执行 --init"),
    "PLAN_OUT_OF_BOUNDS":      (400, "规划分配了名册外 agent", "检查 registry"),
    "CLI_EXECUTION_FAILED":    (502, "CLI 后端执行失败", "检查 CLI 安装"),
    "PROJECT_NOT_FOUND":       (404, "项目不存在", "检查项目 ID"),
    "PROJECT_RUNNING":         (409, "项目正在运行中", "等待完成或先取消"),
    "DELIVERABLE_NOT_FOUND":   (404, "交付物不存在或尚未就绪", "等待任务完成"),
    "INVALID_GOAL":            (400, "Goal 不能为空", "填写项目目标"),
}
```

**验收条件**：
1. 故意触发 workspace 缺失 → Hub 展示可操作文案
2. 配置错误时 → Hub 展示可操作文案
3. 错误响应含 `code`、`message`、`hint`、`doc_url`

---

### 4.3 R2 — Agent Workspace 一体化

#### R2-1 WorkspaceEvent 模型

**设计决策**：新增 `workspace_event` 表。**kernel 只写 `run_event`**（不修改现有写入路径）；Hub 侧 **ProjectionRunner 异步投影** 为 WorkspaceEvent；Hub / Supervisor / Chat 在需要时 **直接写** WorkspaceEvent（如 `project.created`、频道消息）。两表并存，但不是 kernel 同步双写。

**涉及模块**：
- 新建 `backend/common/workspace_events.py`
- 修改 `backend/common/store.py`：新增 `workspace_event`、`projection_state` 表
- 修改 `backend/hub/api/server.py`：新增 WorkspaceEvent API
- 修改 `backend/hub/api/observability_api.py`（如有需要）

**数据模型**：

```sql
CREATE TABLE workspace_event (
    id TEXT PRIMARY KEY,                          -- evt_{timestamp}_{seq}
    type TEXT NOT NULL,                           -- project.task.updated ...
    source TEXT NOT NULL,                         -- kernel/process, hub/chat, ...
    target TEXT,                                  -- channel/project-{id}, direct/{agent}
    payload TEXT NOT NULL,                        -- JSON
    metadata TEXT NOT NULL DEFAULT '{}',          -- JSON {project_id, channel_id, thread_id}
    visibility TEXT NOT NULL DEFAULT 'project',   -- project, workspace, direct
    timestamp TEXT NOT NULL                       -- ISO 8601
);
CREATE INDEX idx_we_project ON workspace_event(json_extract(metadata, '$.project_id'));
CREATE INDEX idx_we_type ON workspace_event(type);
CREATE INDEX idx_we_timestamp ON workspace_event(timestamp);
```

**事件类型枚举**：

```python
class EventType(str, Enum):
    CHAT_MESSAGE_POSTED = "chat.message.posted"
    CHAT_MESSAGE_REPLIED = "chat.message.replied"
    AGENT_STATUS_CHANGED = "agent.status.changed"
    PROJECT_CREATED = "project.created"
    PROJECT_COMPLETED = "project.completed"
    PROJECT_FAILED = "project.failed"
    PROJECT_TASK_UPDATED = "project.task.updated"
    PROJECT_TASK_BLOCKED = "project.task.blocked"
    PROJECT_GATE_COMPLETED = "project.gate.completed"
    PROJECT_GATE_REJECTED = "project.gate.rejected"
    PROJECT_DELIVERABLE_READY = "project.deliverable.ready"
    PROJECT_TRIAGE_REQUESTED = "project.triage.requested"
    RESOURCE_FILE_UPLOADED = "resource.file.uploaded"
    BUDGET_THRESHOLD_REACHED = "budget.threshold.reached"
```

**API 契约**：

```python
# GET /api/workspace/events?project_id=&type=&limit=50&before=
# Response 200:
{
    "events": [
        {
            "id": "evt_20260606_001",
            "type": "project.task.updated",
            "source": "kernel/process",
            "target": "channel/project-p001",
            "payload": {...},
            "metadata": {"project_id": "p001", "channel_id": "channel/project-p001"},
            "timestamp": "2026-06-06T12:00:00Z",
        },
        ...
    ],
}

# GET /api/workspace/events/stream — SSE
# data: {"event": {...}}
```

**前端实现**：

```javascript
// app.js — 时间线 tab（R2 可占位，R3-2 完整 UI）
// SSE /api/workspace/events/stream + filter by project_id
```

**验收条件**：
1. `run_event` 与 `workspace_event` 并存：kernel 写前者，Hub 投影/直写后者
2. GET /api/workspace/events 返回 demo 项目事件
3. SSE /api/workspace/events/stream 可连接
4. 不破坏 AgentEvent/Interaction 契约
5. 时间线 tab **可占位列表**（完整 UI 见 R3-2，与产品规格 R2-1 一致）

#### R2-1a run_event → WorkspaceEvent 投影设计

**设计决策**：kernel 现有 `run_event` 表不修改。在 Hub 侧建投影层，**ProjectionRunner 轮询** Store 中新增的 `run_event` 行，映射并写入 `workspace_event` 表。投影完成后经 EventPipeline 分发（参见 R2-4）。

**为什么要投影而非替换**：
1. kernel 独立于 Hub 运行，`run_event` 是 kernel 的内部真相
2. WorkspaceEvent 是 Hub 侧的增强视图，包含频道、可见性等 Hub 专有字段
3. 投影层允许 kernel 零改动，Hub 逐步增强事件语义而不污染 kernel

**投影映射规则**（基于代码库真实 run_event kind，来源 `process.py`/`task_pipeline.py`/`decision_pipeline.py`/`agent_port.py`）：

```
run_event 表结构：
  id INTEGER PK, interaction_id TEXT, seq INTEGER, kind TEXT, payload TEXT, ts TEXT
  → 无 project_id 列。投影器通过 interaction_id 前缀（`{project_id}:...`）或 interaction 表反查归属。

projection_state 表（checkpoint 专用，不复用 memory 表）：
  CREATE TABLE IF NOT EXISTS projection_state (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL
  );
  -- key='run_event_last_id' → value 为上次投影到的 run_event.id

run_event.kind → WorkspaceEvent.type 映射表

Kernel 任务生命周期：
  run_event.kind = "step_start" (且 payload 含 task_id)
    → type: "project.task.updated"
    → payload: {task_id, status: "running", interaction_id}

  run_event.kind = "step_finish" (且 payload.tokens 存在)
    → type: "project.task.updated"
    → payload: {task_id, status: "awaiting_gate", tokens: payload.tokens}
    → 说明：agent 执行结束，Gate 结果尚未出；与 gate_passed 后的 completed 区分

编排与通知：
  run_event.kind = "auto_create_agents"
    → type: "project.task.updated"
    → payload: {status: "agents_created", agents: payload.agents}

  run_event.kind = "task_split"
    → type: "project.task.updated"
    → payload: {status: "split", parent_task_id: payload.parent_task_id}

  run_event.kind = "message"（project_group notify）
    → 跳过直接投影；由 R2-4 channel_projection_handler 从 run_event 或 conversation 写入频道摘要

CLI 流噪声（跳过，不进 WorkspaceEvent）：
  run_event.kind = "text" | "tool_use" | "tool_result"
    → 跳过

Gate 结果：
  run_event.kind = "gate_passed"
    → type: "project.gate.completed"
    → payload: {interaction_id, gate_type: "execution", result: "passed"}
    → 若检测到 deliverable 文件，同轮追加 project.deliverable.ready（见下方「Hub 侧合成事件」）

  run_event.kind = "gate_failed"
    → type: "project.gate.rejected"
    → payload: {interaction_id, gate_type: "execution", failures: payload.failures}

任务阻塞/失败：
  run_event.kind = "blocked"
    → type: "project.task.blocked"
    → payload: {interaction_id, reason: payload.reason}

  run_event.kind = "plan_rejected"
    → type: "project.task.blocked"
    → payload: {interaction_id, reason: payload.reason, gate_type: "plan"}

  run_event.kind = "split_rejected"
    → type: "project.task.blocked"
    → payload: {interaction_id, reason: payload.reason, gate_type: "split"}

Review：
  run_event.kind = "review_done"
    → type: "project.task.updated"
    → payload: {interaction_id, status: "review_done"}

  run_event.kind = "review_unreachable"
    → type: "project.task.blocked"
    → payload: {interaction_id, reason: payload.reason}

项目生命周期：
  run_event.kind = "cycle_done"
    → type: "project.task.updated"
    → payload: {cycle: extracted_from_interaction_id, status: "cycle_done"}

  run_event.kind = "budget_alert"
    → type: "budget.threshold.reached"
    → payload: {used_pct: payload.used, alert: "warning"}

  run_event.kind = "budget_over"
    → type: "budget.threshold.reached"
    → payload: {used_pct: payload.used, alert: "over"}

断点续跑：
  run_event.kind = "resume_adopted"
    → type: "project.task.updated"
    → payload: {interaction_id, status: "resumed", reason: payload.reason}

Watchdog：
  run_event.kind = "watchdog_soft_idle" | "watchdog_hard_kill"
    → type: "project.task.blocked"
    → payload: {interaction_id, reason: f"watchdog: {kind}", idle_sec: payload.idle_sec}

State snapshot（不投影为 WorkspaceEvent，仅 internal）：
  run_event.kind = "request_snapshot" | "response_snapshot"
    → 跳过，不投影

未匹配的 kind（保留原始 kind 降级投影）：
  → type: "project.task.updated"
  → payload: {raw_kind: kind, raw_payload: payload}

Hub 侧合成事件（无 1:1 run_event kind，投影器 poll_once 或 EventPipeline handler 推断）：

  project.deliverable.ready
    → 触发：gate_passed（execute/review）且 Store 或 deliverables 目录检测到新文件
    → 可与同轮 gate_passed 映射连续 append 第二条 WorkspaceEvent

  project.completed
    → 触发：Supervisor job status=completed；或 cycle_done 且 Store project.status=completed

  project.failed
    → 触发：Supervisor job status=failed；或 budget_over 且 Process 终态为 failed

  project.triage.requested
    → 触发：triage interaction 创建（interaction.kind=triage）；或 plan_rejected 达重试上限路由 triage
```

**project_id 反查逻辑**：

```python
def _resolve_project_id(store, interaction_id: str) -> str | None:
    """从 interaction_id 反查 project_id。

    interaction_id 统一为 ``{project_id}:...``（含合成 id，如 budget/cycle/notify）。
    示例：
      - "p001:t_1:execute:1"     → "p001"
      - "demo-20260606-120000:team_config" → "demo-20260606-120000"
      - "p001:budget"            → "p001"
    """
    if not interaction_id:
        return None
    prefix = interaction_id.split(":", 1)[0]
    if prefix:
        return prefix
    interaction = store.get_interaction(interaction_id)
    return interaction.get("project_id") if interaction else None
```

**投影器实现规格**：

```python
# workspace_events.py — ProjectionRunner

class ProjectionRunner:
    """轮询 Store.run_event → 转换为 WorkspaceEvent 写入。
    
    主路径：定时轮询（2s 间隔），非回调。
    原因：run_kernel 是独立 subprocess，无法同步回调 Hub 进程。
    """

    def __init__(self, store, poll_interval: float = 2.0):
        self.store = store
        self.poll_interval = poll_interval
        self._last_id = self._load_checkpoint()
        self._task = None  # asyncio task

    def _load_checkpoint(self) -> int:
        """从 projection_state 表读取上次投影的 run_event id。"""
        return self.store.get_projection_checkpoint()

    def _save_checkpoint(self, last_id: int):
        """写入投影 checkpoint 到 projection_state 表。"""
        self.store.set_projection_checkpoint(last_id)

    async def poll_once(self) -> int:
        """单次轮询：读取未投影 run_event → 映射 → 写入 workspace_event。返回投影数。"""
        rows = self.store.list_run_events_since(after_id=self._last_id)
        count = 0
        for row in rows:
            project_id = self._resolve_project_id(row["interaction_id"])
            if not project_id:
                continue  # 无法确定归属，跳过
            ws_event = self._map_to_workspace_event(row, project_id)
            if ws_event:
                self.store.append_workspace_event(ws_event)
                count += 1
            self._last_id = max(self._last_id, row["id"])
        self._save_checkpoint(self._last_id)
        return count

    async def start_polling(self):
        """启动轮询循环。"""
        while True:
            await self.poll_once()
            await asyncio.sleep(self.poll_interval)

    def project_all(self, project_id: str) -> int:
        """全量投影某项目的所有 run_event。用于 Hub 启动时补投。"""
        total = 0
        rows = self.store.list_run_events_since(after_id=0)
        for row in rows:
            pid = self._resolve_project_id(row["interaction_id"])
            if pid == project_id:
                ws_event = self._map_to_workspace_event(row, pid)
                if ws_event:
                    self.store.append_workspace_event(ws_event)
                    total += 1
        return total
```

**同步策略**（修正：kernel subprocess 无法同步回调，主路径为轮询）：

| 场景 | 策略 |
|------|------|
| Kernel subprocess 写入 run_event | SQLite 共享文件，kernel 不感知 Hub |
| Hub 侧事件同步 | **主路径**：ProjectionRunner.poll_once() 定时轮询（默认 2s 间隔） |
| Hub 启动时 | 全量扫描未投影 run_event → project_all() → 补投 WorkspaceEvent |
| 前端实时性 | 2s 轮询间隔可配置，SSE 推送时延 ≈ poll_interval + 处理耗时 |

**验收条件**：
1. Kernel run_event 写入后 WorkspaceEvent 自动生成
2. Hub 重启后补投已有 run_event
3. 映射规则覆盖所有 run_event kind
4. 不破坏 kernel run_event 表结构

#### R2-2 频道与线程

**设计决策**：三类会话模型。项目启动时自动创建 `channel/project-{id}`。结构化消息支持 `thread_id`/`parent_id`。@mention 事件落入 WorkspaceEvent。

**涉及模块**：
- `backend/hub/services/channel_service.py`（已有，需扩展）
- `backend/common/store.py`：conversation 表增加 `thread_id`/`parent_id`
- `backend/hub/api/server.py`：频道路由

**数据模型变更**：

```sql
-- conversation 表新增字段
ALTER TABLE conversation ADD COLUMN thread_id TEXT;
ALTER TABLE conversation ADD COLUMN parent_id TEXT;
```

**频道类型**：

```python
CHANNEL_DIRECT = "direct/{agent_id}"           # 单聊
CHANNEL_GENERAL = "channel/general"            # 通用群
CHANNEL_PROJECT = "channel/project-{id}"       # 项目频道
```

**Channels API 契约**：

```python
# GET /api/workspace/channels?project_id=
# Response 200:
{
    "channels": [
        {
            "channel_id": "channel/project-p001",
            "kind": "project",
            "project_id": "p001",
            "title": "项目: 调研报告",
            "member_count": 3,
            "last_activity": "2026-06-06T12:00:00Z",
        },
        ...
    ],
}

# POST /api/workspace/channels
# Request:
{
    "kind": "project",           # project | direct | general
    "project_id": str,           # project 类型必填
    "agent_id": str | None,      # direct 类型必填
    "title": str,
    "members": [str],            # 初始成员列表
}
# Response 201:
{
    "channel_id": "channel/project-p001",
    "created": True,
}

# POST /api/workspace/channels/{channel_id}/messages
# Request:
{
    "content": str,
    "author": str,               # agent_id 或 "user"
    "thread_id": str | None,     # 回复时指定父 thread
    "parent_id": str | None,     # 回复特定消息
}
# Response 201:
{
    "message_id": int,
    "seq": int,
    "created_at": str,
}

# GET /api/workspace/channels/{channel_id}/messages?limit=50&before=
# Response 200:
{
    "messages": [
        {
            "id": 1,
            "seq": 1,
            "role": "agent",
            "author": "researcher",
            "text": "...",
            "thread_id": None,
            "parent_id": None,
            "tokens": 3200,
            "created_at": "2026-06-06T12:00:00Z",
        },
        ...
    ],
}
```

**@mention 事件**：当消息包含 `@agent_id` 时，自动在 WorkspaceEvent 中记录：

```python
# 自动生成的 event:
{
    "type": "chat.message.posted",
    "source": "hub/channel",
    "target": "channel/project-p001",
    "payload": {
        "author": "user",
        "text": "@researcher 请查看报告",
        "mentions": ["researcher"],
        "message_id": 42,
    },
}
```

**验收条件**：
1. 项目启动自动创建 `channel/project-{id}`
2. 项目频道可见 task/gate/deliverable 摘要
3. Context Assembler 可引用频道历史
4. 频道 API 完整（CRUD + 消息 + 列表）

#### R2-3 Job Supervisor + Agents Runtime API

**设计决策**：在 R1-3 的 `jobs` 表基础上扩展。用 Store 标志位替代纯内存 `_KERNEL_RUNS`。Supervisor 模块负责 job 生命周期管理。新增 Agent Runtime 表追踪 agent 实时状态。

**涉及模块**：
- 新建 `backend/common/job_supervisor.py`
- 修改 `backend/common/store.py`：jobs 表完整实现 + agent_runtime 表
- 修改 `backend/hub/api/server.py`：用 Supervisor 替代 `_KERNEL_RUNS`，新增 agent runtime 路由
- 修改 `backend/hub/api/observability_api.py`：Agent 运行时状态路由

**数据模型**：

```python
# store.py — jobs 表完整 schema（R1-3 已建最小版本，此处扩展字段）
# 已存在: job_id, project_id, status, pid, started_at, updated_at, cancel_requested, error
# 扩展: 保留现有字段，增加 Supervisor 逻辑

class JobSupervisor:
    """Job 生命周期管理。替代 _KERNEL_RUNS 内存 dict。"""

    def start_job(self, project_id: str, runner: Callable) -> str:
        """创建 job 记录、启动 runner 线程/进程、返回 job_id"""

    def cancel_job(self, project_id: str) -> bool:
        """设置 cancel_requested=true、发 SIGTERM、等待结束"""

    def get_job(self, project_id: str) -> Optional[dict]:
        """从 Store 查询 job"""

    def list_jobs(self, status: str = None) -> list[dict]:
        """job 列表"""

    def resume_orphans(self) -> list[dict]:
        """扫描 status=running → 标记 orphan → 返回列表"""

# Agent Runtime 状态（可选扩展）
class AgentRuntimeStore:
    """记录 agent runtime 状态。可从 SSE 事件流投影。"""
    def get_agent_status(self, agent_id: str) -> dict: ...
    def set_agent_busy(self, agent_id: str, task_id: str): ...
    def set_agent_idle(self, agent_id: str): ...
```

**Jobs API 契约**：

```python
# GET /api/jobs?project_id=&status=
# Response 200:
{
    "jobs": [
        {
            "job_id": "job_xxxx",
            "project_id": "p001",
            "status": "running",          # pending | running | completed | failed | cancelled | orphan
            "pid": 12345,
            "started_at": "2026-06-06T12:00:00Z",
            "updated_at": "2026-06-06T12:05:00Z",
            "cancel_requested": False,
            "error": None,
        },
        ...
    ],
}

# GET /api/jobs/{job_id}
# Response 200:
{
    "job_id": "job_xxxx",
    "project_id": "p001",
    "status": "running",
    "pid": 12345,
    "started_at": "2026-06-06T12:00:00Z",
    "updated_at": "2026-06-06T12:05:00Z",
    "cancel_requested": False,
    "error": None,
}

# POST /api/projects/{id}/cancel
# Response 200:
{
    "project_id": "p001",
    "cancelled": True,
    "job_status": "cancelled",
}

# POST /api/projects/{id}/run
# 扩展：返回 job_id
# Response 200:
{
    "project_id": "p001",
    "job_id": "job_xxxx",
    "started": True,
}
```

**Agent Runtime API 契约**：

```python
# GET /api/obs/agents
# Response 200:
{
    "agents": [
        {
            "agent_id": "researcher",
            "status": "busy",              # online | idle | busy | error | offline
            "last_seen": "2026-06-06T12:05:00Z",
            "current_task": "t_3",
            "current_project": "p001",
            "backend": "opencode",
            "model": "claude-sonnet-4-6",
            "workspace_ok": True,
        },
        ...
    ],
}

# GET /api/obs/agents/{agent_id}
# Response 200:
{
    "agent_id": "researcher",
    "status": "busy",
    "last_seen": "2026-06-06T12:05:00Z",
    "current_task": "t_3",
    "current_project": "p001",
    "backend": "opencode",
    "model": "claude-sonnet-4-6",
    "workspace_ok": True,
}
```

**Agent Runtime Store 数据模型**：

```sql
CREATE TABLE IF NOT EXISTS agent_runtime (
    agent_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'offline',  -- online|idle|busy|error|offline
    last_seen TEXT,
    current_task TEXT,
    current_project TEXT,
    backend TEXT,
    model TEXT,
    workspace_ok INTEGER DEFAULT 1
);
```

**Agent Runtime 更新策略**：

| 触发事件 | 对应状态更新 |
|----------|-------------|
| Kernel 开始任务 | `set_agent_busy(agent_id, task_id)` → status=busy |
| Kernel 完成任务 | `set_agent_idle(agent_id)` → status=idle |
| SSE 心跳超时 | 自动标记 offline（last_seen > 5min） |
| WorkspaceEvent: agent.status.changed | 投影到 agent_runtime 表 |
| Hub 启动时 | 扫描 agent workspace 路径，填充 workspace_ok |

**验收条件**：
1. Hub 重启后仍知上次 job 状态
2. 取消项目后 Store 有记录
3. Agents 页显示 busy/idle 状态

#### R2-4 事件处理器链

**设计决策**：事件处理管线 `persistence → notification(SSE) → projection → audit`。每个处理器是独立函数，注册到事件类型。处理器失败不污染 kernel task。

**涉及模块**：
- 新建 `backend/common/event_handler.py`

**接口设计**：

```python
# event_handler.py
EventHandler = Callable[[dict], None]

class EventPipeline:
    handlers: dict[str, list[EventHandler]] = {}

    @classmethod
    def register(cls, event_type: str, handler: EventHandler):
        cls.handlers.setdefault(event_type, []).append(handler)

    @classmethod
    def dispatch(cls, event: dict):
        """调度事件给所有注册处理器。处理器异常只 log 不抛出。"""
        for handler in cls.handlers.get(event["type"], []):
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler failed: {e}")

# 注册内置处理器
EventPipeline.register("project.task.updated", persistence_handler)
EventPipeline.register("project.task.updated", sse_notification_handler)
EventPipeline.register("project.task.updated", channel_projection_handler)
EventPipeline.register("project.task.updated", audit_log_handler)
```

**验收条件**：
1. 新增事件类型仅注册 handler，不改多处 SSE 逻辑
2. 处理器失败不污染 kernel task 状态

---

### 4.4 R3 — 体验与可视化升级

#### R3-1 DAG 可视化组件

**设计决策**：纯 SVG 渲染（无外部依赖），从 `GET /api/obs/projects/{id}/tasks` 获取任务树和依赖关系。

**涉及模块**：
- 新建 `frontend/dag-renderer.js`
- 修改 `frontend/app.js`：DAG tab 引入
- 修改 `frontend/style.css`：DAG 样式
- 修改 `frontend/index.html`：DAG 容器

**数据接口**：

```python
# GET /api/obs/projects/{id}/tasks
# Response 包含 tasks 列表，每个 task 含 dependencies
{
    "tasks": [
        {"task_id": "t_1", "name": "调研", "status": "completed",
         "agent": "researcher", "dependencies": [], "token_used": 3200, "duration_s": 45},
        {"task_id": "t_2", "name": "策略制定", "status": "running",
         "agent": "strategist", "dependencies": ["t_1"], "token_used": 1200, "duration_s": 30},
        {"task_id": "t_3", "name": "执行", "status": "blocked",
         "agent": "developer", "dependencies": ["t_1", "t_2"], "token_used": 0, "duration_s": 0},
    ]
}
```

**渲染规格**：

```
SVG 布局参数：
- 节点：圆角矩形 180×50px
- 颜色映射：completed=#22c55e, running=#3b82f6, failed=#ef4444, blocked=#6b7280, pending=#93c5fd
- 边：带箭头 marker，贝塞尔曲线
- 层级布局：拓扑排序 → 分层 → 同层居中
- 交互：节点点击 → 触发 task detail drawer
- 缩放：鼠标滚轮缩放 (transform: scale)
- 平移：拖拽空白区域
```

**验收条件**：
1. demo 项目可见至少 2 节点 DAG
2. failed 节点红色可点
3. 点击节点出现任务详情抽屉

#### R3-2 统一时间线 UI

**设计决策**：基于 R2-1 WorkspaceEvent 的 UI 层。合并 chat/task/gate/deliverable 事件。SSE 增量推送，新事件 2 秒高亮。

**涉及模块**：
- 新建 `frontend/timeline.js`
- 修改 `frontend/app.js`

**渲染规格**：

```javascript
// timeline.js — 时间线渲染
// 格式：
// [12:00:00] [task] 任务 t_1 完成 — 耗时 45s, 3200 tokens  🔵
// [12:01:00] [gate] t_1 通过 Gate 校验                     🟢
// [12:02:00] [deliverable] t_1 交付物已就绪: report.md     📄
// [12:03:00] [chat] researcher: "调研完成，开始策略制定"    💬
//
// 新事件：2 秒淡黄色高亮动画（CSS animation）
// 过滤：按事件类型下拉、按 agent、按时间范围
// SSE：监听 /api/workspace/events/stream
```

**验收条件**：
1. 单次 demo 运行可在时间线看到 created→task_updated→gate→deliverable 序列
2. 事件高亮动画可见

#### R3-3 Onboarding 体验 Polish

**设计决策**：在 R1-3 已实现按钮逻辑的基础上，增加 `GET /api/status` 检测 init 状态，完善空态视觉和引导文案。首次 Demo 完成增加庆祝态。

**涉及模块**：
- `backend/hub/api/server.py`：`GET /api/status` 增强
- `frontend/app.js`：检测 init 状态、庆祝态
- `frontend/index.html`：空态/庆祝态模板
- `frontend/style.css`：空态/庆祝态样式

**API 契约**：

```python
# GET /api/status
# Response 200:
{
    "status": "ok",
    "initialized": True | False,
    "project_count": 3,
    "version": "1.0.0",
}
```

**Home 常规范（非空态）**（产品规格 §5.3 Home 常态）：

```
┌────────────────────────────────────────────────────────────┐
│  🏠 Dashboard                                              │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐              │
│  │ 项目   │ │ 运行中 │ │本月 Token│ │累计成本│              │
│  │   12   │ │    2   │ │  45.2k  │ │ $12.50 │              │
│  │  ↑ 3   │ │  → 0   │ │  ↑ 12%  │ │  ↓ 5%  │  ← 趋势微标 │
│  └────────┘ └────────┘ └────────┘ └────────┘              │
│                                                           │
│  ┌─────────────────────────┐  ┌─────────────────────────┐ │
│  │ 项目 A       🟢 已完成  │  │ 项目 B       🔵 运行中  │ │
│  │ 最后活动: 2 分钟前      │  │ 最后活动: 1 小时前      │ │
│  │ [查看]                  │  │ [查看] [取消]           │ │
│  └─────────────────────────┘  └─────────────────────────┘ │
│                          [+ 新建项目]  [运行 Demo]         │
└────────────────────────────────────────────────────────────┘
```

**趋势微标**：四个统计卡片各带 ↑↓→ 方向 + 百分比。数据来自 `GET /api/status` 扩展返回 `trends` 字段。↑ 绿色、↓ 红色、→ 灰色。无历史数据时不显示。

**API 扩展**：

```python
# GET /api/status — 增加 trends 字段
{
    "status": "ok",
    "initialized": True,
    "project_count": 12,
    "version": "1.0.0",
    "trends": {
        "project_count": {"direction": "up", "value": 3},
        "running_count": {"direction": "flat", "value": 0},
        "monthly_tokens": {"direction": "up", "value": 12},
        "cumulative_cost": {"direction": "down", "value": 5},
    },
}
```

**验收条件**：
1. Home 空态视觉与引导文案达到产品规格 §5.3 终态描述
2. 首次完成 Demo 后有庆祝态或下一步提示
3. 不重复实现 R1-3 按钮逻辑
4. 常规范（非空态）统计卡片带趋势微标

#### R3-4 Chat/Groups UX

**设计决策**：产品规格 §5.3 Chat/Groups 终态。消息三栏结构、轮次分割线、Thinking 可折叠块、@mention 下拉补全、群聊发言人色带、上下文用量指示器。

**涉及模块**：
- `frontend/app.js`：重写 chat + group 渲染函数
- `frontend/style.css`：三栏布局、色带样式、thinking 折叠
- `frontend/index.html`：消息容器结构调整

**Chat 终态渲染规格**（产品规格 §5.3 Chat）：

```
┌────────────────────────────────────────────────────────┐
│  💬 researcher                    [3200 tokens] 12:00  │
│  ┌────────────────────────────────────────────────────┐│
│  │ 调研完成。主要发现：                                ││
│  │ 1. Cursor 适合前端开发                             ││
│  │ 2. Claude Code 适合后端架构                        ││
│  └────────────────────────────────────────────────────┘│
│                                                       │
│  ──── Round 2 ──── 3200 tokens in / 400 out ── 45s ──│
│                                                       │
│  💭 Thinking ─── [collapse]                           │
│  ┌──────────────────────────────────────────────────┐ │
│  │ step_1 → Read file system                        │ │
│  │         ┌─ tool_use: Read ───────────────────┐   │ │
│  │         │ input: {...}  output: "..."         │   │ │
│  │         └────────────────────────────────────┘   │ │
│  │ step_2 → Analyze findings                       │ │
│  │ ...                                              │ │
│  └──────────────────────────────────────────────────┘ │
│                                                       │
│  💬 developer                          [1200 tokens] │
│  ┌────────────────────────────────────────────────────┐│
│  │ 收到调研结果，开始编码                             ││
│  └────────────────────────────────────────────────────┘│
│                                                       │
│  ████████████████░░░░░░  context: 12k / 25k tokens    │
│                                                       │
├────────────────────────────────────────────────────────┤
│  @mention [▸ researcher ▸ developer ▸ strategist ...]  │
│  [input box                         ] [Send ▶]       │
└────────────────────────────────────────────────────────┘
```

**Chat 交互行为规格**：

1. **三栏消息**：左侧 = 角色头像 + 色带（每个 agent 固定色），中间 = 消息内容，右侧 = token 数和时间戳
2. **轮次分割线**：每轮结束时显示分割线，标注：轮次序号、输入/输出 token、耗时
3. **Thinking 块**（产品规格 §3.1 `type=thinking`）：
   - 默认折叠状态，仅显示 `💭 Thinking (3 steps) [expand]`
   - 点击展开：显示 step 列表，每个 step 下是 tool_use + tool_result 的详细内容
   - 支持行号锚点（方便引用）
   - 宽度 100%，不溢出容器
4. **上下文用量指示器**：消息流底部显示进度条，标注当前上下文 token / 最大 token。接近 80% 变黄，100% 变红。
5. **@mention 输入**：
   - 输入 `@` 时弹出候选面板（覆盖层），显示所有可用 agent 列表
   - 支持过滤：继续输入文字缩小范围
   - Tab/↑↓ 选择候选，Enter 确认补全
   - 补全后 `@agent_id` 变为带色标的徽章样式
6. **引用卡片**：当消息包含引用时（`> file.md:42`），渲染为紧凑行内卡片（类似 GitHub 引用）
7. **Agent 列表（左侧栏）**：
   - 头像 / 名称 / 在线状态指示器（绿点/灰点）
   - 当前任务显示（如果有）
   - 点击切换 DM

**Groups 群聊规格**（产品规格 §5.3 Groups）：

```html
<!-- 群聊消息 —— 每条消息显示发言人姓名色带 + 头像 -->
<div class="group-message">
  <div class="msg-sideline" style="border-left: 3px solid #4f46e5"></div>
  <div class="msg-avatar-group">👤</div>
  <div class="msg-body">
    <div class="msg-header">
      <span class="msg-author" style="color: #4f46e5">researcher</span>
      <span class="msg-time">12:00:00</span>
    </div>
    <div class="msg-content">@developer 请查看报告附件</div>
  </div>
  <div class="msg-meta">
    <span class="token-badge">3200 tokens</span>
  </div>
</div>

<!-- @mention 徽章样式 -->
<span class="mention-badge">@developer</span>
```

**验收条件**：
1. @ 输入时出现 agent 列表，可过滤、可选择
2. 群聊可区分发言人（色带 + 头像）
3. Thinking 块可折叠/展开
4. 轮次分割线显示 token 和耗时
5. 上下文用量指示器可见
6. Agent 列表显示在线状态和当前任务

#### R3-5 成本可视化

**设计决策**：基于现有 `GET /api/obs/projects/{id}/cost` 数据，纯 CSS/SVG 实现柱状图和饼图（无外部图表库）。

**涉及模块**：
- 新建 `frontend/cost-chart.js`
- 修改 `frontend/app.js`

**渲染规格**：

```javascript
// 柱状图：按 Agent 分组
// <div class="bar-chart">
//   <div class="bar" style="height: 60%" title="researcher: 12k tokens"></div>
//   <div class="bar" style="height: 100%" title="developer: 20k tokens"></div>
// </div>

// 饼图：<svg> 扇形
// 每个 agent 占一个 sector，颜色不同
// hover 显示 label + token 数

// 预算告警条：
// <div class="budget-bar">
//   <div class="budget-used" style="width: 45%"></div>  <!-- 45% -->
//   <span class="budget-label">已用 45k / 预算 100k</span>
// </div>
// 超过 80%：变黄
// 超过 100%：变红 + 告警文字
```

**验收条件**：
1. 有 token 数据的项目可见柱状图和饼图
2. 预算超过阈值时告警样式变化

#### R3-6 Agent 页与设置页

**设计决策**：产品规格 §5.3 Agents/Settings 终态。Agent 页卡视图（可切换表格），点击进入抽屉编辑。Settings 页 Accordion 分组，CLI 与 Hub 配置关系说明。

**涉及模块**：
- `frontend/app.js`：Agent 卡片渲染、抽屉编辑、Settings Accordion
- `frontend/index.html`：Agent 卡片模板、抽屉模板、Settings 分组模板
- `frontend/style.css`：卡片布局、Accordion 样式

**Agent 页规格**（产品规格 §5.3 Agents）：

```
┌────────────────────────────────────────────────────────────┐
│  Agent 名册                                    [表格视图]  │
│                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ 🔬       │  │ 💻       │  │ 🧪       │  │ 📝       │ │
│  │researcher│  │developer │  │ tester   │  │ content  │ │
│  │ 🟢 busy  │  │ 🟡 idle  │  │ ⚪ error  │  │ 🟢 idle  │ │
│  │opencode  │  │ claude   │  │opencode  │  │opencode  │ │
│  │sonnet-4.6│  │opus-4.8  │  │sonnet-4.6│  │haiku-4.5│ │
│  │research  │  │code-del  │  │test-plan │  │content   │ │
│  │strategy  │  │code-test │  │code-test │  │seo-plan  │ │
│  │          │  │          │  │⚠️ 缺失    │  │          │ │
│  │ t_3: 调研 │  │ (空闲)   │  │ workspace│  │ (空闲)   │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
└────────────────────────────────────────────────────────────┘
```

**Agent 卡片字段**：
| 字段 | 数据来源 |
|------|----------|
| 名称 + 头像 | agents_registry.json |
| 运行时状态 | agent_runtime 表（R2-3）或默认 offline |
| Backend + Model | agents_config.json |
| 能力标签 | agents_registry.json `capabilities`/`task_types` |
| 工作区状态 | 扫描 workspace 目录（正常/缺失/错误） |
| 当前任务 | agent_runtime.current_task（如有） |

**Agent 抽屉编辑规格**：
- 点击卡片 → 弹出右侧抽屉面板
- 抽屉内容：完整 agent 配置（id、name、backend、model、capabilities、workspace 路径）
- 编辑字段：backend（下拉选择）、model（下拉选择）
- 操作：确定（保存）/ 取消（不保存）
- 取消时：关闭抽屉，恢复原值
- 保存时：`POST /api/agents/{agent_id}/config`，成功后刷新卡片

**Settings 页规格**（产品规格 §5.3 Settings）：

```
┌────────────────────────────────────────────────────────────┐
│  Settings                                                 │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ ▶ 系统配置                                           │ │
│  │   端口: 8765    默认 Backend: opencode               │ │
│  │   模型列表: sonnet-4.6 / opus-4.8 / haiku-4.5       │ │
│  └──────────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ ▶ Agent 配置                                        │ │
│  │   注册表路径: business/config/agents_registry.json   │ │
│  │   Workspace基线: business/workspaces/                │ │
│  └──────────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ ▶ CLI 配置                                          │ │
│  │   opencode 路径: ~/.opencode/bin/opencode  ✓ 已登录  │ │
│  │   claude   路径: ~/.claude/claude       ✗ 未安装   │ │
│  │   ❓ CLI 和 Hub 的关系说明                            │ │
│  └──────────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ ▶ 网络                                              │ │
│  │   绑定地址: 127.0.0.1    鉴权 Token: [未设置]        │ │
│  └──────────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ ▶ 关于                                              │ │
│  │   版本: 1.0.0    API 文档: /docs   术语说明          │ │
│  └──────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

**Accordion 交互**：点击头部 ▶ 展开/折叠分组。同一时间可展开多个分组。每个分组内为键值对列表 + 输入框（可编辑项）。

**验收条件**：
1. 误编辑可取消（关闭抽屉后值不变）
2. Settings 无大面积空白卡片
3. Agent 卡片显示运行时状态
4. Agent 能力标签正确展示
5. CLI 配置显示登录状态检测结果

#### R3-7 前端/CSS 模块化

**设计决策**：按产品规格 §7.3/§7.4 拆分。CSS 拆 `tokens.css/layout.css/components.css/pages.css`；JS 拆 `ui-core.js/chat.js/projects.js/agents.js/groups.js/settings.js`。

**涉及模块**：
- 拆分 `frontend/style.css` → 4 个 CSS 文件
- 拆分 `frontend/app.js` → 6 个 JS 模块（保留 `app.js` 作为入口）

**模块化方案**：

```html
<!-- index.html — 新加载顺序 -->
<link rel="stylesheet" href="/static/tokens.css">
<link rel="stylesheet" href="/static/layout.css">
<link rel="stylesheet" href="/static/components.css">
<link rel="stylesheet" href="/static/pages.css">

<script src="/static/markdown.js"></script>
<script src="/static/dag-renderer.js"></script>
<script src="/static/timeline.js"></script>
<script src="/static/cost-chart.js"></script>
<script src="/static/ui-core.js"></script>
<script src="/static/chat.js"></script>
<script src="/static/projects.js"></script>
<script src="/static/agents.js"></script>
<script src="/static/groups.js"></script>
<script src="/static/settings.js"></script>
<script src="/static/app.js"></script>
```

*注：`dag-renderer.js`（R3-1 DAG 图）、`timeline.js`（R3-2 时间线）、`cost-chart.js`（R3-5 成本图表）为 R3 新增前端模块，被 projects.js 引用，需在 projects.js 前加载。*

**验收条件**：
1. JS 主文件 <800 行
2. CSS 单文件 <600 行

#### R3-8 亮色主题重构

**设计决策**：在现有 `[data-theme=light]` 基础上，100% 覆盖所有 CSS 变量。暖白 `#f8f9fa→#ffffff`，毛玻璃改为半透明白 + 阴影，主色 `#4f46e5`。

**涉及模块**：
- `frontend/style.css`（或 `tokens.css` 拆分后）

**验收条件**：
1. `[data-theme=light]` 变量 100% 覆盖关键路径

#### R3-9 删除项目

**设计决策**：基于现有 `DELETE /api/projects/{id}` 路由（已实现），增加二次确认对话框。运行中项目拒绝删除。

**涉及模块**：
- `backend/hub/api/server.py`：已有 DELETE 路由，确认逻辑
- `frontend/app.js`：二次确认对话框
- `frontend/index.html`：确认对话框模板

**验收条件**：
1. 删除后项目从列表消失
2. 误删有确认对话框
3. 运行中项目删除前先取消或拒绝并提示

---

### 4.5 R4 — 资源层与对外能力（按需）

#### R4-1 共享资源索引

**设计决策**：资源索引统一管理 file/context/skill/tool 四类元数据。与现有 deliverables/KB/skills 双写兼容，不替换现有存储。

**涉及模块**：
- 新建 `backend/common/resource_index.py`
- 新建 `backend/hub/api/resource_api.py`

**数据模型**：

```sql
CREATE TABLE resource (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,         -- file|context|skill|tool
    project_id TEXT,
    task_id TEXT,
    path TEXT,
    mime TEXT,
    size INTEGER,
    meta TEXT DEFAULT '{}',
    created_at TEXT
);
CREATE INDEX idx_r_project ON resource(project_id);
CREATE INDEX idx_r_type ON resource(type);
```

**API 契约**：

```python
# GET /api/resources?project_id=&type=&limit=50
# Response 200:
{
    "resources": [
        {
            "id": "res_xxxx",
            "type": "file",
            "project_id": "p001",
            "task_id": "t_1",
            "path": "deliverables/report.md",
            "mime": "text/markdown",
            "size": 1234,
            "meta": {},
            "created_at": "2026-06-06T12:00:00Z",
        },
    ],
}
```

#### R4-2 项目文件上传

**设计决策**：Hub 支持上传文件挂到 project/channel/task 上下文。文件注入 worker prompt 供 agent 引用。

**涉及模块**：
- 新建 `backend/hub/api/resource_api.py`（与 R4-1 共享）
- 修改 `backend/common/context_assembler.py`：注入文件引用到 prompt

**API 契约**：

```python
# POST /api/projects/{id}/files
# Request: multipart/form-data
#   file: binary (max 10MB)
#   task_id: str | None (可选，挂到特定 task)
#   description: str | None (可选，给 agent 的说明)
# Response 201:
{
    "resource_id": "res_xxxx",
    "path": "uploads/report.pdf",
    "size": 123456,
    "mime": "application/pdf",
}

# GET /api/resources?project_id=p001&type=file
# 返回该项目的所有上传文件 + 交付物文件
```

**约束**：
- 文件大小上限：10MB（配置可调）
- 类型白名单：`text/*`, `image/*`, `application/pdf`, `application/json`, `text/csv`, `text/markdown`
- 存储位置：`business/tasks/project/{id}/uploads/`
- 文件引用注入 prompt 格式：`[file:uploads/report.pdf] (description)`

**验收条件**：
1. 上传文件出现在频道 + 资源列表
2. agent 任务可引用上传文件

#### R4-3 Workspace Manifest

**涉及模块**：
- `backend/hub/api/server.py`：新增 `GET /.well-known/myteam.json`

**API 契约**：

```python
# GET /.well-known/myteam.json
# Response 200:
{
    "workspace": {"id": "myteam-workspace", "version": "1.0.0"},
    "api": {"base_url": "http://localhost:8765", "version": "v1"},
    "backends": ["opencode", "claude"],
    "agents": [
        {"id": "main", "capabilities": ["team_config", "task_plan", "triage"]},
        {"id": "researcher", "capabilities": ["research", "strategy"]},
    ],
    "task_types": ["team_config", "task_plan", "research", "strategy", "evaluate", "review", "triage"],
    "sse_endpoints": ["/api/workspace/events/stream", "/api/obs/projects/{id}/events"],
    "auth_mode": "optional",
}
```

**验收条件**：外部脚本可读 manifest 发现 API

#### R4-4 可选鉴权

**涉及模块**：
- `backend/hub/api/server.py`：添加 middleware

**实现规格**：

```python
# server.py — 可选鉴权 middleware
# 读取环境变量 MYTEAM_API_TOKEN
# 如果未设置：不启用鉴权
# 如果已设置：所有 API 请求需携带 Authorization: Bearer <token>
# 默认 bind 127.0.0.1，0.0.0.0 需 opt-in（文档警告）

from fastapi import Request, HTTPException
import os

API_TOKEN = os.environ.get("MYTEAM_API_TOKEN")

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if API_TOKEN:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != API_TOKEN:
            raise HTTPException(status_code=401, detail="Unauthorized")
    return await call_next(request)
```

**验收条件**：开启 token 后无 token 请求 401

#### R4-5/R4-6 MetaGPT B/C

**涉及模块**：
- `backend/common/agent_transport.py`：`build_worker_prompt` 增强
- `backend/common/plan_expansion.py`：运行时展开

**R4-5 结构化 prompt 规格**：

```python
# agent_transport.py — build_worker_prompt 增强
# 对 execute/review 增加三段结构：
def build_worker_prompt(task_type: str, context: dict) -> str:
    sections = []
    
    # Section 1: 信息收集
    sections.append("## 信息收集\n请先确认你已掌握以下信息：")
    sections.append(f"- 目标：{context.get('goal', '')}")
    sections.append(f"- 输入：{context.get('input', '')}")
    sections.append(f"- 已有交付物：{context.get('deliverables', [])}")
    
    # Section 2: 产出要求
    spec = registry.get_spec(task_type)
    sections.append(f"\n## 产出要求\n任务类型：{task_type}")
    sections.append(f"交付物模板：{spec.get('deliverable_template', {})}")
    sections.append(f"校验规则：{spec.get('check_rules', {})}")
    
    # Section 3: 自检清单
    sections.append(f"\n## 自检清单\n提交前请确认：")
    sections.append("1. 所有必需章节已完整")
    sections.append("2. 数据/引用有来源标注")
    sections.append("3. 输出格式符合模板要求")
    
    return "\n\n".join(sections)
```

**R4-6 运行时展开规格**：

```python
# plan_expansion.py — PlanExpander.expand_at_runtime
# 触发条件：needs_review=True 且任务范围超过阈值
# 行为：原地展开子 DAG（深度上限 3）
# 超限：走 triage 流程

class PlanExpander:
    MAX_DEPTH = 3
    
    def expand_at_runtime(self, task: dict, depth: int = 0) -> list[dict]:
        if depth >= self.MAX_DEPTH:
            return self._route_to_triage(task)
        # 展开：生成子 task DAG
        subtasks = self._decompose(task)
        # Gate 校验子 DAG
        for st in subtasks:
            if not self.gate.check(st):
                return self._route_to_triage(task)
        return subtasks
```

**验收条件**：
1. 集成测或 snapshot 测 prompt 含三段结构
2. 单测覆盖展开后 Gate 仍校验
3. 深度超限走 triage

#### R4-7 Chat 附件上传（可选）

**设计决策**：Chat 输入区支持上传小文件。文件进入 `resource/file` 索引（依赖 R4-1）。单聊上下文可引用。**非 R1–R3 MVP 阻塞**，未做此功能不视为升级未完成。

**涉及模块**：
- `frontend/app.js`：输入区附件按钮 + 上传逻辑
- `frontend/index.html`：附件按钮 + 文件预览
- `backend/hub/api/resource_api.py`：上传 endpoint（复用 R4-2）

**API 契约**：

```python
# POST /api/chat/{agent_id}/attachments
# Request: multipart/form-data: file (max 5MB)
# Response 201:
{
    "resource_id": "res_xxxx",
    "path": "chat_attachments/report.pdf",
    "mime": "application/pdf",
    "size": 123456,
}

# 上传后：
# 1. 文件落入 resource/file 索引（R4-1）
# 2. 系统自动在 chat 中插入一条消息：
#    "[附件] report.pdf (123KB) — 下一轮对话 agent 可引用"
# 3. Context Assembler 引用附件路径
```

**约束**：
- 文件大小上限：5MB（小于 R4-2 的 10MB，因为走 chat 上下文）
- 类型白名单：`text/*`, `image/*`, `application/pdf`, `image/png`, `image/jpeg`, `text/csv`, `text/markdown`
- 存储位置：`business/tasks/project/{project_id}/chat_attachments/`
- 同一会话中上传的文件在下一轮 agent 交互中可用

**验收条件**：
1. 上传后 agent 下一轮可见文件引用
2. 未做 R4-7 时 Chat 底部无附件按钮亦视为合规

---

## 5. 需求-设计-实现追溯矩阵

### 5.1 R0 追溯

| 产品需求 | 设计决策 | 实现模块 | 测试覆盖 | 验收项 |
|----------|----------|----------|----------|--------|
| R0-1 修复测试回归 | SSE timeout/mock | test_observability_api.py | pytest 全绿 | `pytest backend -q` <60s |
| R0-2 修复交付物 API | bundle 路径对齐 | store.py, server.py | 2 例修复 | Hub 可读 demo deliverable |
| R0-3 引入 CI | scripts/test.sh + GitHub Actions | 新建脚本 | CI 阻断合并 | CLAUDE.md 记录 |
| R0-4 FastAPI lifespan | @asynccontextmanager | server.py | 无 deprecated 警告 | 启动无警告 |

### 5.2 R1 追溯

| 产品需求 | 设计决策 | 实现模块 | 测试覆盖 | 验收项 |
|----------|----------|----------|----------|--------|
| R1-1 Demo 目录化 | business/demo/ 目录 | run_kernel.py | 集成测 | --demo <5min exit 0 |
| R1-2 CLI 友好错误 | ERROR_MAP + 进度条 | process.py, run_kernel.py | 5 类错误单测 | 无堆栈、进度摘要 |
| R1-3 Hub 建项/启项 | API + jobs 表 + 线程 | server.py, project_service.py, app.js | 新建项目 API 测 | Hub 独立完成 Demo |
| R1-4 交付物闭环 | 文件树+预览面板 | store.py, observability.py, app.js | deliverable API 测 | Hub 浏览交付物 |
| R1-5 友好错误 | APIError + exception handler | server.py | 错误响应断言 | Hub 展示可操作文案 |

### 5.3 R2 追溯

| 产品需求 | 设计决策 | 实现模块 | 测试覆盖 | 验收项 |
|----------|----------|----------|----------|--------|
| R2-1 WorkspaceEvent | events 表 + 投影/Hub 直写 | workspace_events.py, store.py | events CRUD + SSE | API/SSE 可查询；时间线 tab 可占位 |
| R2-1a run_event 投影 | ProjectionRunner 轮询 + 映射表 | workspace_events.py | 投影映射完整覆盖 | 16+ kind 映射正确 |
| R2-2 频道与线程 | 三类会话 + thread_id | channel_service.py, store.py | 频道 CRUD | 项目频道可见摘要 |
| R2-3 Job Supervisor | 替代 _KERNEL_RUNS | job_supervisor.py | job 生命周期 | 重启后可知状态 |
| R2-4 事件处理器链 | pipeline + 注册 | event_handler.py | 处理链注册/分发 | 新增事件不修改 SSE |

### 5.4 R3 追溯

| 产品需求 | 设计决策 | 实现模块 | 测试覆盖 | 验收项 |
|----------|----------|----------|----------|--------|
| R3-1 DAG 图 | SVG 纯前端 | dag-renderer.js | 组件渲染测 | 2 节点 DAG 可见 |
| R3-2 时间线 UI | WorkspaceEvent 视图 | timeline.js | 事件渲染测 | 完整事件序列 |
| R3-3 Onboarding | 检测 init + 庆祝态 | app.js | 状态检测 | 空态终态描述 |
| R3-4 Chat UX | 三栏 + @mention | app.js, style.css | 交互功能测 | @mention 工作 |
| R3-5 成本图 | CSS/SVG 纯前端 | cost-chart.js | 图表渲染测 | 柱/饼图可见 |
| R3-6 Agent/设置 | 抽屉+Accordion | app.js | UI 功能测 | 可取消编辑 |
| R3-7 模块化 | 4 CSS + 6 JS | 多文件拆分 | 页面加载测 | 文件行数约束 |
| R3-8 亮色主题 | 100% 变量覆盖 | tokens.css | 变量覆盖检查 | 双主题完整 |
| R3-9 删除项目 | 二确对话框 | app.js, server.py | API + UI 测 | 删除+二确 |

### 5.5 R4 追溯

| 产品需求 | 设计决策 | 实现模块 | 测试覆盖 | 验收项 |
|----------|----------|----------|----------|--------|
| R4-1 共享资源索引 | resource 表统一元数据 | resource_index.py, resource_api.py | CRUD 测 | 项目资源列表含交付物+上传文件 |
| R4-2 项目文件上传 | multipart POST → uploads/ | resource_api.py, context_assembler.py | 上传+引用测 | 文件出现在频道+资源列表 |
| R4-3 Manifest | GET /.well-known/myteam.json | server.py | 内容正确性 | 外部脚本可发现 API |
| R4-4 可选鉴权 | middleware + env token | server.py | token 测 | 401 阻断 |
| R4-5 结构化 prompt | build_worker_prompt 三段 | agent_transport.py | snapshot 测 | prompt 含三段结构 |
| R4-6 运行时展开 | PlanExpander + 深度上限 3 | plan_expansion.py | 展开后 Gate 校验 | 超限走 triage |
| R4-7 Chat 附件上传 | 5MB + 类型白名单 | resource_api.py, app.js | 上传+引用测 | agent 下一轮可见引用 |

---

## 6. 测试规格

### 6.1 测试策略

| 层级 | 工具 | 覆盖目标 | 速度目标 |
|------|------|----------|----------|
| Unit | pytest | 模块级逻辑（Store CRUD、Gate 校验、契约验证） | <30s |
| Integration | pytest + httpx | API 路由、SSE 流、错误响应 | <20s |
| UI | 手动 + 截图对比 | 页面完整性、交互流、主题 | 按需 |
| E2E | run_kernel + Hub 启动 | 完整 Demo 流程 | <5min |

### 6.2 测试用例清单

#### R0 测试用例

| ID | 优先级 | 类型 | 描述 | 关联需求 |
|----|--------|------|------|----------|
| T-R0-1 | P0 | Unit | `pytest backend -q` 全量通过 <60s | R0-1 |
| T-R0-2 | P0 | Integration | SSE endpoint 终态 timeout 不超 30s | R0-1 |
| T-R0-3 | P0 | Integration | `test_deliverable_read` 通过 | R0-2 |
| T-R0-4 | P0 | Integration | `test_deliverable_file_read` 通过 | R0-2 |
| T-R0-5 | P1 | Unit | 启动无 DeprecationWarning | R0-4 |
| T-R0-6 | P1 | Unit | auto-resume 行为不变 | R0-4 |

#### R1 测试用例

| ID | 优先级 | 类型 | 描述 | 关联需求 |
|----|--------|------|------|----------|
| T-R1-1 | P0 | E2E | `--init` + `--demo` exit 0, <5min | R1-1 |
| T-R1-2 | P0 | Integration | Demo 完成后 deliverable 目录存在 | R1-1 |
| T-R1-3 | P0 | Unit | FileNotFoundError → 正确中文消息 | R1-2 |
| T-R1-4 | P0 | Unit | CalledProcessError → 正确中文消息 | R1-2 |
| T-R1-5 | P0 | Unit | 无对应映射的异常 → 通用错误消息 | R1-2 |
| T-R1-6 | P0 | Unit | 错误写入 run_event | R1-2 |
| T-R1-7 | P0 | Integration | POST /api/projects 创建并返回 project_id | R1-3 |
| T-R1-8 | P0 | Integration | POST /api/projects/{id}/run 启动并返回 started=true | R1-3 |
| T-R1-9 | P0 | Integration | POST /api/init 返回 success=true | R1-3 |
| T-R1-10 | P0 | Integration | POST /api/demo 返回 project_id | R1-3 |
| T-R1-11 | P0 | Integration | GET /api/obs/projects/{id}/deliverables 返回文件列表 | R1-4 |
| T-R1-12 | P0 | Integration | GET /api/obs/projects/{id}/deliverables/{path} 返回文件内容 | R1-4 |
| T-R1-13 | P0 | Integration | 请求不存在路径 → 404 error | R1-4 |
| T-R1-14 | P0 | Integration | POST /api/projects/{id}/deliverables/{path}/mark-final 标记成功 | R1-4 |
| T-R1-15 | P0 | Integration | 标记最终后再次查询 is_final=true | R1-4 |
| T-R1-16 | P0 | Integration | 无 API token 请求 → 友好错误 + doc_url | R1-5 |
| T-R1-17 | P0 | Integration | 不存在项目请求 → 404 + hint | R1-5 |
| T-R1-18 | P1 | Integration | 空 goal 创建项目 → 400 INVALID_GOAL | R1-5 |

#### R2 测试用例

| ID | 优先级 | 类型 | 描述 | 关联需求 |
|----|--------|------|------|----------|
| T-R2-1 | P0 | Unit | workspace_events 表 CRUD | R2-1 |
| T-R2-2 | P0 | Unit | 投影：run_event 写入后 workspace_event 可查询 | R2-1 |
| T-R2-3 | P0 | Integration | GET /api/workspace/events 返回事件列表 | R2-1 |
| T-R2-4 | P0 | Integration | SSE /api/workspace/events/stream 可连接 | R2-1 |
| T-R2-5 | P0 | Integration | 按 project_id 过滤 events | R2-1 |
| T-R2-6 | P0 | Unit | 频道 CRUD（direct/general/project） | R2-2 |
| T-R2-7 | P0 | Integration | 项目启动自动创建 channel/project-{id} | R2-2 |
| T-R2-8 | P0 | Unit | 消息 thread_id 支持 | R2-2 |
| T-R2-9 | P0 | Unit | job 创建/查询/取消 | R2-3 |
| T-R2-10 | P0 | Integration | POST /api/projects/{id}/cancel → Store 标记 | R2-3 |
| T-R2-11 | P0 | Unit | Hub 重启后 orphan 检测 | R2-3 |
| T-R2-12 | P0 | Unit | EventPipeline 注册/分发 | R2-4 |
| T-R2-13 | P0 | Unit | 处理器异常不抛出 | R2-4 |
| T-R2-14 | P1 | Unit | 新增事件类型只需注册 handler | R2-4 |
| T-R2-15 | P0 | Unit | ProjectionRunner 轮询读未投影 run_event | R2-1a |
| T-R2-16 | P0 | Integration | run_event 投影为 WorkspaceEvent 后可通过 API 查 | R2-1a |
| T-R2-17 | P0 | Unit | 投影映射覆盖所有已知 run_event kind + Hub 合成事件 | R2-1a |
| T-R2-18 | P0 | Integration | ProjectionRunner checkpoint 在重启后不重复投影 | R2-1a |
| T-R2-19 | P0 | Integration | GET /api/workspace/channels 返回频道列表 | R2-2 |
| T-R2-20 | P0 | Integration | POST /api/workspace/channels 创建频道 | R2-2 |
| T-R2-21 | P0 | Integration | POST /api/workspace/channels/{id}/messages 发消息 | R2-2 |
| T-R2-22 | P0 | Integration | GET /api/jobs 返回 job 列表 | R2-3 |
| T-R2-23 | P0 | Integration | GET /api/jobs/{id} 返回单个 job | R2-3 |
| T-R2-24 | P0 | Integration | GET /api/obs/agents 返回 agent 运行时状态 | R2-3 |
| T-R2-25 | P0 | Integration | GET /api/obs/agents/{id} 返回单个 agent 状态 | R2-3 |

#### R3 测试用例

| ID | 优先级 | 类型 | 描述 | 关联需求 |
|----|--------|------|------|----------|
| T-R3-1 | P0 | Unit | DAG 节点着色正确 | R3-1 |
| T-R3-2 | P0 | Unit | DAG 依赖边方向正确 | R3-1 |
| T-R3-3 | P0 | E2E | Demo 项目 DAG 图可见 ≥2 节点 | R3-1 |
| T-R3-4 | P0 | Unit | 时间线事件序列排序正确 | R3-2 |
| T-R3-5 | P0 | E2E | 时间线可见 created→task→gate→deliverable | R3-2 |
| T-R3-6 | P1 | Unit | GET /api/status 返回 initialized 状态 | R3-3 |
| T-R3-7 | P1 | E2E | 首次 Demo 完成 → 庆祝态 | R3-3 |
| T-R3-8 | P0 | E2E | @mention 弹出 agent 列表 | R3-4 |
| T-R3-9 | P0 | E2E | 群聊消息显示发言人 | R3-4 |
| T-R3-10 | P0 | Unit | 成本柱状图数据正确 | R3-5 |
| T-R3-11 | P0 | Unit | 预算告警阈值正确（80%/100%） | R3-5 |
| T-R3-12 | P1 | E2E | Agent 抽屉编辑可取消 | R3-6 |
| T-R3-13 | P1 | E2E | Settings 分组可展开/折叠 | R3-6 |
| T-R3-14 | P1 | Unit | JS 主文件 <800 行 | R3-7 |
| T-R3-15 | P1 | Unit | CSS 单文件 <600 行 | R3-7 |
| T-R3-16 | P1 | E2E | 切换亮色主题无样式断裂 | R3-8 |
| T-R3-17 | P1 | Unit | [data-theme=light] 变量完整 | R3-8 |
| T-R3-18 | P0 | Integration | DELETE /api/projects/{id} 状态码 200 | R3-9 |
| T-R3-19 | P0 | E2E | 删除项目有二次确认 | R3-9 |
| T-R3-20 | P0 | Integration | 运行中项目拒绝删除 | R3-9 |

#### R4 测试用例

| ID | 优先级 | 类型 | 描述 | 关联需求 |
|----|--------|------|------|----------|
| T-R4-1 | P1 | Unit | 资源索引 CRUD | R4-1 |
| T-R4-2 | P1 | Integration | GET /api/resources 返回项目资源列表 | R4-1 |
| T-R4-3 | P1 | Integration | POST /api/projects/{id}/files 上传文件成功 | R4-2 |
| T-R4-4 | P1 | Integration | 上传文件出现在资源列表 | R4-2 |
| T-R4-5 | P1 | Integration | 超过大小限制的文件上传被拒绝 | R4-2 |
| T-R4-6 | P1 | Integration | 不在白名单的文件类型被拒绝 | R4-2 |
| T-R4-7 | P1 | Integration | GET /.well-known/myteam.json 返回正确内容 | R4-3 |
| T-R4-8 | P1 | Integration | 开启 token 后无 token 请求 401 | R4-4 |
| T-R4-9 | P1 | Integration | 开启 token 后有正确 token 请求 200 | R4-4 |
| T-R4-10 | P2 | Unit | build_worker_prompt 含三段结构 | R4-5 |
| T-R4-11 | P2 | Unit | PlanExpander 深度上限 3 | R4-6 |
| T-R4-12 | P2 | Unit | 展开后 Gate 仍校验 | R4-6 |
| T-R4-13 | P2 | Integration | Chat 附件上传成功 | R4-7 |
| T-R4-14 | P2 | Integration | 上传后 agent 下一轮可见文件引用 | R4-7 |
| T-R4-15 | P2 | Integration | 未实现时不显示附件按钮 | R4-7 |

### 6.3 测试环境要求

```bash
# 1. 单元测试和集成测试
export MYTEAM_ROOT="/path/to/repo"
export PYTHONPATH="$MYTEAM_ROOT/backend"
venv/bin/python3 -m pytest backend -q -v

# 2. E2E 测试（Demo 完整流程）
export MYTEAM_ROOT="/path/to/repo"
export PYTHONPATH="$MYTEAM_ROOT/backend"
venv/bin/python3 backend/common/run_kernel.py --init
venv/bin/python3 backend/common/run_kernel.py --demo

# 3. Hub 集成测试
./run.sh start
# 手动或 httpx 测试 API
```

### 6.4 测试门禁

| 关卡 | 条件 | 阻断谁 |
|------|------|--------|
| PR 提交 | `pytest backend -q` 全绿 | PR 合并 |
| R0→R1 | pytest <60s 全绿 | 所有 R1 功能 PR |
| R1→R2 | Demo 跑通 + 交付物可预览 | R2 功能 PR |
| R2→R3 | WorkspaceEvent API 可用 + job 可取消 | R3 功能 PR |
| R3→R4 | §14.5 页面清单可演示 | R4 功能 PR |
| 最终验收 | 全部 P0 测试通过 + §14 验收逐项勾选 | 合并到 main |

---

## 7. 附录：关键接口签名速查

### 7.1 Store 新增/修改方法

```python
# store.py — 新增
def create_job(self, project_id: str, pid: int) -> str
def update_job_status(self, job_id: str, status: str, error: str = None)
def get_job(self, project_id: str) -> dict | None
def list_jobs(self, status: str = None) -> list[dict]
def cancel_job(self, project_id: str) -> bool

def append_workspace_event(self, event: dict) -> str
def list_workspace_events(self, project_id: str = None, type: str = None, limit: int = 50, before: str = None) -> list[dict]

def get_project_deliverables(self, project_id: str) -> dict  # 已有，需修复

# ── ProjectionRunner 投影所需 ──
#
# 现有方法（不新增）：
#   list_run_events(interaction_id)           → 按 interaction 查
#   list_project_events(project_id)           → 已聚合项目所有 run_event（推荐）
#
# 新增方法（投影轮询用）：
def list_run_events_since(self, after_id: int, limit: int = 200) -> list[dict]
  """读取 run_event 表中 id > after_id 的行，按 id 升序。投影器轮询用。"""

def get_projection_checkpoint(self) -> int
def set_projection_checkpoint(self, last_id: int)
  """读写 projection_state 表，key='run_event_last_id'。不复用 memory 表（id 为 INTEGER AUTOINCREMENT）。"""
```

### 7.2 路径常量（paths.py 扩展）

```python
# paths.py — 新增
DEMO_DIR = BUSINESS_DIR / "demo"              # business/demo/
DEMO_GOAL_FILE = DEMO_DIR / "goal.txt"        # business/demo/goal.txt
DEMO_AGENTS_CONFIG = DEMO_DIR / "agents_config.json"

WELL_KNOWN_DIR = STATIC_DIR / ".well-known"   # 用于 manifest
```

### 7.3 事件类型枚举

```python
# workspace_events.py
class EventType(str, Enum):
    CHAT_MESSAGE_POSTED = "chat.message.posted"
    CHAT_MESSAGE_REPLIED = "chat.message.replied"
    AGENT_STATUS_CHANGED = "agent.status.changed"
    PROJECT_CREATED = "project.created"
    PROJECT_COMPLETED = "project.completed"
    PROJECT_FAILED = "project.failed"
    PROJECT_TASK_UPDATED = "project.task.updated"
    PROJECT_TASK_BLOCKED = "project.task.blocked"
    PROJECT_GATE_COMPLETED = "project.gate.completed"
    PROJECT_GATE_REJECTED = "project.gate.rejected"
    PROJECT_DELIVERABLE_READY = "project.deliverable.ready"
    PROJECT_TRIAGE_REQUESTED = "project.triage.requested"
    RESOURCE_FILE_UPLOADED = "resource.file.uploaded"
    BUDGET_THRESHOLD_REACHED = "budget.threshold.reached"
```

---

*本文档与产品规格同步更新。设计变更时需同时更新 §5 追溯矩阵和 §6 测试规格。*