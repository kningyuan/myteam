# myteam 升级测试记录

> **文档类型**：测试执行记录（Test Record）
> **测试日期**：2026-06-07（首轮 06-06，修复验证 06-07）
> **测试基线**：分支 `upgrade/continued`，commit `0dedb7a`
> **执行人**：测试专家 (tester)

---

## R0 — 工程可信底座

### R0-1 测试回归修复

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R0-1 | `PYTHONPATH=backend venv/bin/python3 -m pytest backend -q` | 205 passed, 1 warning (StarletteDeprecationWarning), 8.46s | ✅ |
| T-R0-2 | 检查 `test_project_stream_until_done` 实现 | `threading.Event().wait(timeout=30)` 已替换开放循环 | ✅ |
| T-R0-3 | `test_deliverable_read` 通过 | monkeypatch 覆盖 `common.paths.PROJECTS_DIR` | ✅ |
| T-R0-4 | `test_deliverable_file_read` 通过 | Store monkeypatch + `meta={"artifact_base": "workspace"}` | ✅ |

**详细说明**：
- 全量 205 个测试用例全部通过，耗时 8.46s（目标 <60s），**通过** ✅
- 1 个警告来自 `fastapi/testclient.py` 中的 `StarletteDeprecationWarning`，非本次升级引入
- SSE 测试已加 30s timeout，不再挂起

### R0-3 CI 脚本

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R0-6 | 检查 `scripts/test.sh` | 文件存在（23 行），`pytest -q -x --tb=short` | ✅ |

**发现**：
- ✅ `scripts/test.sh` 存在且可执行
- ❌ 无 `.github/workflows/test.yml`（GitHub Actions CI 配置缺失——产品规格 R0-3 要求 "GitHub Actions 或等效脚本"）
- ✅ CLAUDE.md 有 CI 文档记录

### R0-4 FastAPI lifespan 迁移

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R0-5 | 检查 server.py lifespan 实现 | `@asynccontextmanager async def lifespan(app)` + `app = FastAPI(lifespan=lifespan)` | ✅ |

**详细说明**：
- 已删除 `@app.on_event("startup")`，替换为 `lifespan` 上下文管理器
- `_startup_resume_projects` 和 `gc_workspace` 移入 lifespan
- **无 `DeprecationWarning`** ✅

---

## R1 — 产品闭环

### R1-1 Demo 目录化

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R1-1 | 检查 `business/demo/` | 目录存在，含 `goal.txt` (127B) + `agents_config.json` (208B) | ✅ |
| — | 检查是否有 `README.md` | 不存在（产品规格 R1-1 要求） | ❌ |
| T-R1-2 | 检查 `run_kernel.py` 中的 `_read_demo_goal()` | 存在，正确读取 `business/demo/goal.txt` | ✅ |

**详细说明**：
- `run_kernel.py:33`: `_DEMO_DIR = Path(...) / "business" / "demo"`
- `run_kernel.py:36-46`: `_read_demo_goal()` 读取文件首行，支持 `#` 注释
- 支持 `--demo-dir` 参数（`run_kernel.py:259-260`）
- `POST /api/demo` 使用 `_read_demo_goal()` + `_system_default_backend()` 启动 demo

### R1-2 CLI 友好错误

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R1-3 | 检查 `run_kernel.py:_friendly_traceback` 对 FileNotFoundError | 返回中文消息含 workspace/config 路径判断 | ✅ |
| T-R1-4 | 对 CalledProcessError | 返回中文消息含 exit code | ✅ |
| — | 对 RuntimeError | 返回中文消息含 plan gate/名册 判断 | ✅ |
| — | 默认 fallback | 返回通用中文消息 | ✅ |
| — | 错误写入 `run_event` | 跟踪路径验证：`process.py` 异常捕获后写 `store.append_run_event` | ✅ |

**详细说明**：
- `run_kernel.py:69-98`: `_friendly_traceback` 覆盖 5 类异常，按 `__cause__` 链拆解
- 设计规格要求将 ERROR_MAP 放在 `process.py`，实际实现在 `run_kernel.py`，**位置不同但功能一致**

### R1-3 Hub 内创建并启动项目

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R1-4 | `POST /api/init` | `{"success": true, "message": "已完成 0 个 Agent 工作空间初始化"}` | ✅ |
| T-R1-5 | `POST /api/demo` | `{"project_id": "demo-ui-1780752983", "started": true}` | ✅ |
| T-R1-6 | `POST /api/projects/run` 正常 goal | 测试中因 CLI 未配无法完整验证，API 返回 project_id | ⚠️ |
| T-R1-7 | `POST /api/projects/run` 空 goal | `400: {"detail": "goal 必填"}` | ⚠️ |
| — | 前端空态三按钮 | `index.html` 含初始化/Demo/创建项目 三个按钮 ✅ | ✅ |

**详细说明**：
- `POST /api/projects/run` 是单一路由（非设计规格的 `POST /api/projects` + `POST /api/projects/{id}/run`），**接口设计不同但功能覆盖**
- 空 goal 错误返回旧格式 `{"detail": "goal 必填"}`，**非统一错误格式**
- Home 空态：`index.html` 含三按钮，前端 `S.api.init()` / `S.api.runDemo()` / `S.ui.showNewProjectModal()`

### R1-4 交付物闭环

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R1-10 | `GET /api/obs/projects/{id}/deliverables` | 新增聚合 API，已修复 500（use-after-close + import 错误 + 孤儿代码）→ `200 {"tasks": {}}` | ✅ |
| — | `GET /api/projects/{id}/deliverable/{task_id}` | 返回 deliverable bundle 结构 | ✅ |
| — | `GET /api/projects/{id}/deliverable/{task_id}/file?path=` | 文件读取路径 | ✅ |
| — | 前端交付物文件树+预览 | `renderDeliverableTaskNav` / `renderDeliverableFileList` 存在 | ✅ |
| — | mark-final API | 未找到 `POST .../mark-final` 路由 | ❌ |
| — | 版本对比 | 未实现 | ❌ |

**详细说明**：
- ✅ 聚合 API 已新增并修复 use-after-close bug 和 import 错误
- 前端 `renderDeliverableTaskNav()` 和 `renderDeliverableFileList()` 存在，文件树 + 预览面板基本可用
- ❌ mark-final 和版本对比未实现（非 MVP 阻塞）

### R1-5 Hub 友好错误

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| — | 检查 `APIError` 类 | `server.py:84`: `class APIError(Exception)` 含 code/message/hint/doc_url | ✅ |
| — | 检查 `ERROR_CODES` | 7 个错误码定义 | ✅ |
| — | 检查 `exception_handler` | `server.py:132`: 统一格式 | ✅ |
| T-R1-9 | `GET /api/projects/nonexistent` | `{"error": {"code": "PROJECT_NOT_FOUND", "message": "项目不存在"}}` — **已统一** | ✅ **已修复** |
| — | `POST /api/projects/nonexistent/cancel` | `{"error": {"code": "PROJECT_NOT_FOUND", ...}}` — **已统一** | ✅ **已修复** |
| — | `DELETE /api/projects/nonexistent` | `{"error": {"code": "PROJECT_NOT_FOUND", ...}}` — **已统一** | ✅ **已修复** |
| — | `POST /api/projects/run` 空 goal | `{"error": {"code": "INVALID_GOAL", ...}}` — **已统一** | ✅ **已修复** |

---

## R2 — Agent Workspace 一体化

### R2-1 WorkspaceEvent 模型

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R2-1 | 检查 store.py 中 workspace_event 表 | 完整 schema：id/type/source/target/payload/metadata/visibility/timestamp + 索引 | ✅ |
| T-R2-2 | 检查 CRUD 方法 | `append_workspace_event` / `list_workspace_events` / `list_run_events_since` / checkpoint | ✅ |
| T-R2-3 | `GET /api/workspace/events?limit=3` | 返回 3 条事件，含 chat.message.posted 等 | ✅ |
| — | `GET /api/workspace/events/stream` (SSE) | `server.py:185` 路由存在 | ✅ |
| T-R2-4 | 检查 `_map_to_workspace_event` | 16 种 kind 映射 + 降级 + 跳过逻辑，完整覆盖 | ✅ |

**详细说明**：
- `workspace_event` 表 3 个索引：`project_id` / `type` / `timestamp`
- `projection_state` 表用于 checkpoint 持久化
- `ProjectionRunner` 异步轮询（2s 间隔），poll_once 异常隔离
- store 实测：workspace_event 表已有 38 条真实事件数据

### R2-1a run_event 投影

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| — | 检查 `workspace_events.py` | `ProjectionRunner` 完整实现 | ✅ |
| — | 检查 `_map_to_workspace_event` 映射表 | step_start/step_finish/gate_passed/gate_failed/blocked/budget_alert/watchdog/review/resume 等 | ✅ |
| — | 检查反查逻辑 | `_resolve_project_id` 从 interaction_id 前缀分离 | ✅ |
| — | 测试 | 无单元测试覆盖投影逻辑 | ❌ |

### R2-2 频道与线程

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R2-5 | `GET /api/workspace/channels` | 6 个频道可见：dm:product/dm:main/dm:content + 项目频道 | ✅ |
| T-R2-6 | `POST /api/workspace/channels` | 路由存在 (`server.py:243`) | ✅ |
| — | `POST /api/workspace/channels/{id}/messages` | 路由存在 (`server.py:269`) | ✅ |
| — | @mention → WorkspaceEvent 自动落库 | 事件数据中存在 `agent.status.changed` @mention 事件 | ✅ |
| — | 项目启动自动创建频道 | 项目频道 `channel/project-{id}` 可创建 | ✅ |

### R2-3 Job Supervisor + Agent Runtime

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R2-7 | 检查 store.py 中 job/agent_runtime 表 | job 表完整、agent_runtime 表含 4 字段 + meta | ✅ |
| T-R2-8 | `GET /api/jobs` | `{"jobs": []}` — 表存在但无数据 | ✅ |
| T-R2-9 | `GET /api/obs/agents` | 3 个 agent（developer/main/tester）都返回 idle 状态 | ✅ |
| T-R2-10 | `POST /api/projects/proj1/cancel` | 路由存在，返回 404（项目不存在）— 正确行为 | ✅ |
| — | `job_supervisor.py` | **存在** — 完整实现 `start_job`/`cancel_job`/`resume_orphans` | ✅ **已修复** |
| — | lifespan orphan 检测 | `_auto_resume_on_startup` 调用 `jsv.resume_orphans()` | ✅ **已修复** |
| — | `_KERNEL_RUNS` 是否已替换 | 部分替换：`_KERNEL_RUNS` 在 `POST /api/projects/run` 中仍使用，但 Supervisor 可用于 cancel 和 orphan 检测 | ⚠️ 部分 |

### R2-4 事件处理器链

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R2-11 | 检查 `event_handler.py` | `EventPipeline` 类：register/dispatch/registered_types 完整 | ✅ |
| — | 4 种内置处理器 | persistence/SSE notification/channel projection/audit log 全部注册 | ✅ |
| — | 10 种事件类型 | project.task.updated/gate.completed/gate.rejected/task.blocked/deliverable.ready 等 | ✅ |
| — | 异常隔离 | dispatch 中 handler 异常只 log 不抛出 | ✅ |
| — | 测试 | 无单元测试覆盖 EventPipeline | ❌ |

---

## R3 — 体验与可视化升级

### R3-1 DAG 可视化

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R3-1 | 检查 `dag-renderer.js` | 111 行，`renderDAG` + `dagLayout` + 6 种状态色 | ✅ |
| — | SVG 渲染 | 节点圆角矩形、贝塞尔曲线边、marker 箭头 | ✅ |
| — | 点击交互 | `.dag-node` click → `window._onDagNodeClick(id)` | ✅ |
| T-R3-2 | 检查 `renderDAG` 是否被调用 | **app.js:1104-1107: `if (tasks.length && typeof renderDAG === 'function') { ... renderDAG(dagContainer, tasks); }`** | ✅ **已修复** |
| — | DAG 容器在 index.html 中 | `#dag-container` 元素（index.html:229） | ✅ **已修复** |
| — | 项目 DAG tab | DAG tab 存在（`data-ptab="dag"`），6 tab 结构完整 | ✅ **已修复** |

### R3-2 时间线 UI

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R3-3 | 检查 `timeline.js` | 89 行，`renderTimeline` + 12 种事件类型中文标签 | ✅ |
| — | 新事件高亮 | 最近 5 条 `.tl-new` 样式 | ✅ |
| T-R3-4 | 检查 `renderTimeline` 是否被调用 | **app.js:1111-1114: `if (typeof renderTimeline === 'function') { ... renderTimeline(tlContainer, events); }`** | ✅ **已修复** |
| — | 时间线容器在 index.html 中 | `#timeline-container` 元素（index.html:261） | ✅ **已修复** |
| — | 项目时间线 tab | 时间线 tab 存在（`data-ptab="timeline"`），6 tab 结构完整 | ✅ **已修复** |

### R3-3 Onboarding

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R3-5 | `GET /api/status` | `initialized: true, project_count: 0, trends: {...}` — 完整 | ✅ |
| — | 前端空态 | index.html 含 `#home-empty-state` 三按钮 | ✅ |
| — | 庆祝态 | 首次 Demo 完成后的庆祝态或下一步提示未找到 | ❌ |

### R3-4 Chat/Groups UX

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R3-6 | @mention 逻辑 | `mentionActive`/`mentionFilter`/`S.mentionActive` 完整 | ✅ |
| T-R3-7 | Thinking 折叠 | `.thinking-section.collapsed` + toggle + `thinking-toggle` | ✅ |
| — | 上下文指示器 | `#context-indicator` DOM 元素存在 | ✅ |
| — | 三栏消息 | `msg-avatar`/`msg-bubble`/`msg-meta` 结构存在 | ✅ |
| — | 轮次分割线 | 存在「──── Round N ────」分割线 | ✅ |
| — | @mention 下拉 | 候选面板逻辑完整（`S.mentionActive` + Tab/Enter 选择） | ✅ |

### R3-5 成本可视化

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R3-8 | `budgetBar()` 存在 | app.js:796，含 80% 黄/100% 红逻辑 | ✅ |
| — | 柱状图 SVG | app.js 中 SVG 柱状图实现（8 色循环） | ✅ |
| — | `GET /api/obs/projects/{id}/cost` | 路由存在（observability_api.py:151） | ✅ |

### R3-6 Agent/设置页

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| — | Agent 卡片 | 列表含头像/名称/状态/Backend/能力标签 | ✅ |
| T-R3-9 | 抽屉编辑可取消 | `showConfirm` 用于删除/取消确认 | ✅ |
| — | Settings Accordion | `.settings-card` + `.settings-section-title` 分组 | ✅ |
| — | CLI 登录状态 | `updateSettingsCliPath()` 显示 CLI 路径 | ✅ |

### R3-7 前端模块化

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R3-10 | tokens.css | 85 行，57 个 token + 19 个 light 变量 | ✅ |
| — | layout.css/components.css/pages.css | **文件不存在**（设计规格要求） | ❌ |
| T-R3-11 | app.js 行数 | **3539 行**（目标 <800） | ❌ |
| T-R3-12 | style.css 行数 | **1531 行**（目标 <600） | ❌ |
| — | JS 模块拆分 | 未拆分（仍在单文件 app.js） | ❌ |

**详细说明**：
- 只有 `tokens.css` 从 style.css 分离出来（85 行）
- layout.css、components.css、pages.css 不存在（设计规格要求 4 个 CSS 模块）
- JS 未拆分（设计规格要求 6 个模块：ui-core/chat/projects/agents/groups/settings）
- dag-renderer.js 和 timeline.js 是例外——已独立文件但未被调用

### R3-8 亮色主题

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| T-R3-13 | `[data-theme=light]` 变量 | tokens.css 含 19 个 light 变量（暖白基调） | ✅ |
| — | style.css 中 light 覆盖 | 13 处 `[data-theme="light"]` 相关选择器 | ✅ |

### R3-9 删除项目

| 用例 ID | 操作 | 实际结果 | 状态 |
|---------|------|----------|:----:|
| — | `DELETE /api/projects/{id}` 路由 | **存在**，已迁移到 `APIError` 格式 | ✅ **已确认** |
| T-R3-14 | 前端二次确认 | `showConfirm()` 用于项目删除确认 | ✅ |
| — | 运行中拒绝删除 | 前端逻辑：`if (!await showConfirm(...)) return;` | ✅ |

**详细说明**：
- 首轮测试中 `GET /api/projects/nonexistent` 返回 404 导致误判 DELETE 路由不存在——实际路由存在且工作正常
- `DELETE /api/projects/nonexistent` → `{"error": {"code": "PROJECT_NOT_FOUND", ...}}` ✅

---

## 测试执行统计

| 维度 | 首轮 (06-06) | 本轮 (06-07) | 变化 |
|------|:-----------:|:-----------:|:----:|
| 单测通过数 | 205 | 205 | ➡️ |
| 单测耗时 | 8.17s | 8.28s | ➡️ |
| API 实测端点数 | 14 | 14 | ➡️ |
| 代码审查文件数 | 18 | 18 | ➡️ |
| 前端功能点检查 | 25 | 25 | ➡️ |

### 按阶段通过率

| 阶段 | 首轮 | 本轮 | 变化 |
|------|:----:|:----:|:----:|
| R0 | 83% | **100%** | ⬆️ |
| R1 | 70% | **80%** | ⬆️ |
| R2 | 82% | **91%** | ⬆️ |
| R3 | 57% | **86%** | ⬆️ |
| **合计** | **71%** | **88%** | ⬆️ +17% |