# myteam 后端 API 文档（前端消费视角）

> **版本**：v1.0  
> **基干代码**：分支 `upgrade/continued`，commit `0dedb7a`  
> **生成日期**：2026-06-07  
> **覆盖范围**：`backend/hub/api/server.py` + `observability_api.py`  
> **阅读对象**：前端开发者 / 集成测试 / 新 Agent 对接

---

## 目录

1. [系统与状态](#1-系统与状态)
2. [Workspace 事件](#2-workspace-事件)
3. [频道与消息](#3-频道与消息)
4. [项目](#4-项目)
5. [交付物](#5-交付物)
6. [Job（运行任务）](#6-job运行任务)
7. [Agent 运行时](#7-agent-运行时)
8. [Agent 配置与管理](#8-agent-配置与管理)
9. [Chat（单聊）](#9-chat单聊)
10. [Groups（群组）](#10-groups群组)
11. [可观测（Observability）](#11-可观测observability)
12. [配置与后端](#12-配置与后端)

---

## 1. 系统与状态

### 1.1 Hub 健康检查

```
GET /
```

前端加载 Hub 时的入口。返回 `index.html` SPA。

**响应**：`FileResponse(STATIC_DIR / "index.html")`

---

### 1.2 系统状态

```
GET /api/status
```

Home 仪表盘加载时调用。检测初始化状态 + 统计概览 + 趋势微标数据。

**响应 200**：
```json
{
  "status": "ok",
  "initialized": true,
  "project_count": 12,
  "running_count": 2,
  "version": "1.0.0",
  "trends": {
    "project_count": {"direction": "up", "value": 3},
    "running_count": {"direction": "flat", "value": 0},
    "monthly_tokens": {"direction": "up", "value": 12},
    "cumulative_cost": {"direction": "down", "value": 5}
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `initialized` | bool | Agent workspace 是否已初始化 |
| `project_count` | int | 项目总数 |
| `running_count` | int | 运行中项目数 |
| `trends.*.direction` | string | `up` / `down` / `flat` |
| `trends.*.value` | int | 变化量 |

---

### 1.3 初始化 Agent 工作空间

```
POST /api/init
```

Home 空态「初始化 Agent」按钮触发。

**响应 200**：
```json
{"success": true, "message": "已完成 12 个 Agent 工作空间初始化"}
```

---

### 1.4 启动 Demo

```
POST /api/demo
```

Home 空态「运行 Demo」按钮触发。后台线程启动编排，立即返回。

**响应 200**：
```json
{"project_id": "demo-ui-1712345678", "started": true}
```

**使用流程**：
1. 前端调用 → 获得 `project_id`
2. 自动切换到 Projects tab
3. 调用 `GET /api/projects/run-status/{project_id}` 轮询完成状态

---

## 2. Workspace 事件

### 2.1 查询事件

```
GET /api/workspace/events?project_id=&type=&limit=50
```

时间线 tab 加载时调用。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `project_id` | string | 否 | 按项目过滤 |
| `type` | string | 否 | 按事件类型过滤 |
| `limit` | int | 否 | 最大条数（默认 50，上限 200） |

**响应 200**：
```json
{
  "events": [
    {
      "id": "evt_20260607_0001",
      "type": "project.task.updated",
      "source": "kernel/process",
      "target": "channel/project-p001",
      "payload": "{\"status\": \"completed\", \"tokens\": 3200}",
      "metadata": "{\"project_id\": \"p001\", \"channel_id\": \"channel/project-p001\"}",
      "visibility": "project",
      "timestamp": "2026-06-07T12:00:00Z"
    }
  ]
}
```

**事件类型枚举**：

| type | 含义 | payload 关键字段 |
|------|------|-----------------|
| `project.created` | 项目创建 | — |
| `project.completed` | 项目完成 | — |
| `project.failed` | 项目失败 | — |
| `project.task.updated` | 任务状态更新 | `status`, `interaction_id`, `tokens` |
| `project.task.blocked` | 任务阻塞 | `reason`, `gate_type` |
| `project.gate.completed` | 门禁通过 | `interaction_id` |
| `project.gate.rejected` | 门禁拒绝 | `failures` |
| `project.deliverable.ready` | 交付物就绪 | — |
| `project.triage.requested` | 升级处理 | — |
| `chat.message.posted` | 聊天消息 | `author`, `text`, `mentions` |
| `budget.threshold.reached` | 预算告警 | `used_pct`, `alert` (`warning`/`over`) |

---

### 2.2 事件 SSE 流

```
GET /api/workspace/events/stream?project_id=
```

时间线 tab 实时更新。长连接 SSE，2s 轮询间隔。

**事件格式**：
```json
data: {"id":"evt_...","type":"project.task.updated","payload":"...","timestamp":"..."}
```

**keepalive**：
```
: keepalive
```

---

## 3. 频道与消息

### 3.1 频道列表

```
GET /api/workspace/channels?project_id=
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `project_id` | string | 否 | 按项目过滤 |

**响应 200**：
```json
{
  "channels": [
    {
      "channel_id": "channel/project-p001",
      "kind": "project",
      "project_id": "p001",
      "title": "项目: 调研报告",
      "last_activity": "2026-06-07T12:00:00Z"
    }
  ]
}
```

---

### 3.2 创建频道

```
POST /api/workspace/channels
```

**请求体**：
```json
{
  "kind": "project",
  "project_id": "p001",
  "title": "项目: 调研报告",
  "members": ["researcher", "developer"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `kind` | string | 是 | `project` / `direct` / `general` |
| `project_id` | string | project 类型必填 | 项目 ID |
| `agent_id` | string | direct 类型必填 | Agent ID |
| `title` | string | 否 | 频道标题 |
| `members` | [string] | 否 | 初始成员 |

**响应 201**：
```json
{"channel_id": "channel/project-p001", "created": true}
```

---

### 3.3 频道消息列表

```
GET /api/workspace/channels/{channel_id}/messages?limit=50
```

**响应 200**：
```json
{
  "messages": [
    {
      "id": 1,
      "seq": 1,
      "role": "agent",
      "author": "researcher",
      "text": "调研报告已完成",
      "thread_id": null,
      "parent_id": null,
      "tokens": 3200,
      "created_at": "2026-06-07T12:00:00Z"
    }
  ]
}
```

---

### 3.4 发送频道消息

```
POST /api/workspace/channels/{channel_id}/messages
```

**请求体**：
```json
{
  "content": "@researcher 请查看报告",
  "author": "user"
}
```

**自动行为**：消息含 `@agent_id` 时，自动生成 `chat.message.posted` WorkspaceEvent。

**响应 201**：
```json
{"message_id": 2, "seq": 2, "created_at": "2026-06-07T12:01:00Z"}
```

---

## 4. 项目

### 4.1 项目列表

```
GET /api/projects
```

**响应 200**：
```json
{"projects": [{"project_id": "p001", "title": "调研报告", "status": "completed", ...}]}
```

---

### 4.2 项目详情

```
GET /api/projects/{project_id}
```

**错误**：
```json
{"error": {"code": "PROJECT_NOT_FOUND", "message": "项目不存在", "hint": "检查项目 ID"}}
```

---

### 4.3 创建并运行项目

```
POST /api/projects/run
```

**请求体**：
```json
{
  "goal": "调研 AI 编码工具…",
  "title": "可选标题",
  "mode": "one_shot",
  "budget": 100000,
  "review": false
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `goal` | string | **是** | 项目目标 |
| `title` | string | 否 | 标题 |
| `mode` | string | 否 | `one_shot` / `recurring` |
| `budget` | int | 否 | Token 上限 |
| `review` | bool | 否 | 是否开启评审 |

**响应 200**：
```json
{"project_id": "ui_调研_20260607_120000", "title": "调研报告", "started": true}
```

**错误**：
```json
{"error": {"code": "INVALID_GOAL", "message": "Goal 不能为空", "hint": "填写项目目标"}}
```

---

### 4.4 查询运行状态

```
GET /api/projects/run-status/{project_id}
```

Demo 启动后前端轮询此接口。

**响应**：
```json
{"running": false, "error": null}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `running` | bool | 是否正在运行 |
| `error` | string/null | 错误信息（运行失败时） |

---

### 4.5 取消项目

```
POST /api/projects/{project_id}/cancel
```

**响应 200**：
```json
{"project_id": "p001", "status": "cancelled"}
```

### 4.6 删除项目

```
DELETE /api/projects/{project_id}
```

**约束**：运行中的项目拒绝删除（返回 409）。

**响应 200**：
```json
{"success": true, "project_id": "p001", "interactions": 5, "files_removed": 0}
```

---

### 4.7 续跑项目

```
POST /api/projects/{project_id}/resume
```

断点续跑已中断的项目。

---

## 5. 交付物

### 5.1 项目级交付物聚合列表

```
GET /api/obs/projects/{project_id}/deliverables
```

交付物 tab 加载时调用，返回所有任务的交付物文件树。

**响应 200**：
```json
{
  "project_id": "p001",
  "tasks": {
    "t_1": {
      "task_id": "t_1",
      "name": "调研",
      "agent": "researcher",
      "status": "completed",
      "deliverables": [
        {"path": "report.md", "size": 1234, "mime": "text/markdown", "kind": "doc"},
        {"path": "data.csv", "size": 5678, "mime": "text/csv", "kind": "data"}
      ],
      "primary": "# 报告标题…（前 200 字摘要）"
    }
  }
}
```

---

### 5.2 任务级交付物包

```
GET /api/projects/{project_id}/deliverable/{task_id}
```

返回单个任务的完整交付物包（含主文档 + 文件清单）。

**响应 200**：
```json
{
  "task_id": "t_1",
  "agent_id": "researcher",
  "task_type": "research",
  "base": "document",
  "exists": true,
  "content": "# 报告标题\n正文…",
  "files": [
    {"path": "report.md", "name": "report.md", "size": 1234, "kind": "doc"}
  ]
}
```

---

### 5.3 单文件读取

```
GET /api/projects/{project_id}/deliverable/{task_id}/file?path=report.md
```

读取交付物包中的单个文件。用于在预览面板展示文件内容。

**响应 200**：
```json
{
  "exists": true,
  "path": "report.md",
  "content": "文件内容…（纯文本或 Markdown）"
}
```

---

## 6. Job（运行任务）

### 6.1 Job 列表

```
GET /api/jobs?status=
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `status` | string | 过滤：`running` / `completed` / `failed` / `cancelled` / `orphan` |

**响应 200**：
```json
{
  "jobs": [
    {
      "job_id": "job_1712345678_p001",
      "project_id": "p001",
      "status": "running",
      "pid": 12345,
      "started_at": "2026-06-07T12:00:00Z",
      "updated_at": "2026-06-07T12:05:00Z",
      "cancel_requested": false,
      "error": null
    }
  ]
}
```

---

### 6.2 Job 详情

```
GET /api/jobs/{job_id}
```

---

## 7. Agent 运行时

### 7.1 全部 Agent 运行时状态

```
GET /api/obs/agents
```

Agents 页面加载时调用。

**响应 200**：
```json
{
  "agents": [
    {
      "agent_id": "researcher",
      "status": "busy",
      "last_seen": "2026-06-07T12:05:00Z",
      "current_task": "t_3",
      "current_project": "p001",
      "backend": "opencode",
      "model": "claude-sonnet-4-6",
      "workspace_ok": true
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | `online` / `idle` / `busy` / `error` / `offline` |
| `workspace_ok` | bool | 工作空间目录是否存在且完整 |

### 7.2 Agent 运行时详情

```
GET /api/obs/agents/{agent_id}
```

不存在时返回离线状态的默认值。

---

## 8. Agent 配置与管理

### 8.1 Agent 列表

```
GET /api/agents
```

**响应 200**：
```json
{"agents": [{"id": "researcher", "name": "调研专家", "backend": "claude", "model": "sonnet-4-6"}]}
```

### 8.2 Agent 配置（单个）

```
GET /api/agents/{agent_id}/config
POST /api/agents/{agent_id}/config
```

**POST 请求体**：
```json
{"backend": "claude", "model": "claude-sonnet-4-6"}
```

### 8.3 批量应用模型

```
POST /api/agents/apply-model
```

### 8.4 Agent 详情

```
GET /api/agents/{agent_id}/detail
```

返回 Workspace 文件列表。

### 8.5 Agent 聊天记录

```
GET /api/agents/{agent_id}/chats
```

### 8.6 删除 Agent

```
DELETE /api/agents/{agent_id}
```

### 8.7 更新 Agent

```
PUT /api/agents/{agent_id}/manage
```

### 8.8 创建 Agent（AI 生成）

```
POST /api/agents/create
```

从自然语言描述生成 Agent。

### 8.9 Agent ID 建议

```
GET /api/agents/suggest-id?description=
```

### 8.10 Agent 注册表

```
GET /api/agents/registry
```

### 8.11 通知 Agent

```
POST /api/agents/{agent_id}/notify
```

### 8.12 向项目派发

```
POST /api/projects/{project_id}/dispatch
```

---

## 9. Chat（单聊）

### 9.1 SSE Chat 流

```
GET /api/chat/{agent_id}
```

Web SSE 流式对话。发送消息通过 URL 参数 `?text=...`。

### 9.2 消息历史

```
GET /api/chat/{agent_id}/messages
```

### 9.3 清空上下文

```
POST /api/chat/{agent_id}/clear
```

### 9.4 归档 / 恢复

```
POST /api/chat/{agent_id}/archive
POST /api/chat/{agent_id}/restore
```

### 9.5 搜索归档

```
GET /api/chat/archives/search
```

---

## 10. Groups（群组）

### 10.1 群组列表

```
GET /api/groups
```

### 10.2 创建群组

```
POST /api/groups
```

### 10.3 搜索群组

```
GET /api/groups/search
```

### 10.4 群组详情

```
GET /api/groups/{group_id}
```

### 10.5 解散 / 恢复群组

```
POST /api/groups/{group_id}/dissolve
POST /api/groups/{group_id}/restore
```

### 10.6 绑定项目

```
POST /api/groups/{group_id}/bind-project
```

### 10.7 成员管理

```
POST   /api/groups/{group_id}/members
DELETE /api/groups/{group_id}/members/{agent_id}
```

### 10.8 清空消息

```
POST /api/groups/{group_id}/clear
```

### 10.9 Group SSE Chat

```
GET /api/groups/{group_id}/chat
```

### 10.10 群组事件流

```
GET /api/groups/{group_id}/events
```

### 10.11 删除群组

```
DELETE /api/groups/{group_id}
```

---

## 11. 可观测（Observability）

所有 `obs` 路由挂载在独立 router 下，前缀 `api/obs`。

### 11.1 项目总览

```
GET /api/obs/projects/{project_id}/overview
```

项目工作台「概览」tab 的核心数据源。

**响应 200**：
```json
{
  "project_id": "p001",
  "title": "调研",
  "status": "in_progress",
  "mode": "one_shot",
  "progress": 0.5,
  "task_counts": {"running": 1, "completed": 2, "pending": 1},
  "tasks": [{"id": "t_1", "name": "调研", "agent": "researcher", "status": "completed", "token_used": 3200, "dependencies": []}],
  "tokens": 12400,
  "budget": 100000,
  "budget_ratio": 0.124,
  "budget_state": "ok"
}
```

### 11.2 项目列表（可观测视图）

```
GET /api/obs/projects
```

### 11.3 摘要

```
GET /api/obs/summary
```

Home 仪表盘统计卡片的数据源。

**响应 200**：
```json
{
  "totals": {"projects": 5, "running": 2, "tokens": 45000},
  "projects": [
    {"id": "p001", "title": "调研", "status": "completed", "progress": 1.0, "task_count": 3, "tokens": 12000}
  ]
}
```

### 11.4 Task Types

```
GET /api/obs/task-types
```

返回所有注册的 task_type 及其配置。

### 11.5 知识库

```
GET /api/obs/memory
```

### 11.6 成本明细

```
GET /api/obs/projects/{project_id}/cost
```

成本 tab 数据源。

**响应 200**：
```json
{
  "project": 12400,
  "by_agent": {"researcher": 3200, "developer": 5600, "strategist": 3600},
  "by_task": {"t_1": 3200, "t_2": 3600, "t_3": 5600}
}
```

### 11.7 项目事件流

```
GET /api/obs/projects/{project_id}/events
```

### 11.8 项目 SSE 流

```
GET /api/obs/projects/{project_id}/stream
```

2s 轮询 SSE，仅在状态/任务/token 变化时推数据。终态后收尾。

### 11.9 舰队状态

```
GET /api/obs/projects/{project_id}/fleet
```

概览页 Agent 舰队摘要。

### 11.10 任务详情

```
GET /api/obs/projects/{project_id}/tasks/{task_id}
```

含该任务的所有 interaction 列表。

### 11.11 Interaction 时间线

```
GET /api/obs/interactions/{interaction_id}/timeline
```

### 11.12 Interaction 事件 SSE

```
GET /api/obs/interactions/{interaction_id}/events
```

轮询单个 interaction 的 run_event，终态后收尾。

---

## 12. 配置与后端

### 12.1 后端列表

```
GET /api/backends
```

返回所有可用 CLI 后端及其模型列表。

**响应 200**：
```json
{
  "backends": [
    {"id": "opencode", "name": "OpenCode", "models": [{"id": "claude-sonnet-4-6", "name": "Sonnet 4.6"}]},
    {"id": "claude", "name": "Claude Code", "models": []}
  ]
}
```

### 12.2 系统配置

```
GET  /api/config
PUT  /api/config
```

### 12.3 Skill 配置

```
GET  /api/skill-config
PUT  /api/skill-config
```

---

## 附录 A：前端页面 ↔ API 映射

| 前端页面 | 页面加载时调用的 API |
|----------|---------------------|
| **Home 仪表盘** | `GET /api/status` (趋势) + `GET /api/obs/summary` (统计+项目列表) |
| **Home 空态** | 无 API（检测 `projects.length === 0`）→ 三按钮（Init / Demo / 建项） |
| **Chat 列表** | `GET /api/agents` |
| **Chat 对话** | `GET /api/chat/{agent_id}` (SSE) + `GET /api/chat/{agent_id}/messages` (历史) |
| **Groups 列表** | `GET /api/groups` |
| **Groups 对话** | `GET /api/groups/{group_id}/chat` (SSE) |
| **Projects 列表** | `GET /api/projects` + `GET /api/obs/projects` |
| **项目概览 tab** | `GET /api/obs/projects/{id}/overview` + `GET /api/obs/projects/{id}/cost` + `GET /api/obs/projects/{id}/fleet` |
| **项目 DAG tab** | `GET /api/obs/projects/{id}/overview` (tasks 字段含 dependencies) |
| **项目执行 tab** | `GET /api/obs/projects/{id}/events` + `GET /api/obs/projects/{id}/stream` (SSE) |
| **项目时间线 tab** | `GET /api/workspace/events?project_id={id}` + `GET /api/workspace/events/stream` (SSE) |
| **项目交付物 tab** | `GET /api/obs/projects/{id}/deliverables` + `GET /api/projects/{id}/deliverable/{task_id}/file` |
| **项目成本 tab** | `GET /api/obs/projects/{id}/cost` |
| **Agents 管理页** | `GET /api/agents` + `GET /api/obs/agents` (运行时状态) |
| **Settings 页** | `GET /api/config` + `GET /api/skill-config` + `GET /api/backends` |
| **新建项目模态框** | `POST /api/projects/run` |
| **取消/删除项目** | `POST /api/projects/{id}/cancel` + `DELETE /api/projects/{id}` |

## 附录 B：统一错误格式

所有核心项目/状态 API 使用统一错误格式：

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "用户可读的错误描述",
    "hint": "建议的修复操作",
    "doc_url": "/docs/troubleshooting.html#error-code"
  }
}
```

| 错误码 | HTTP | 说明 | 触发场景 |
|--------|:----:|------|----------|
| `INVALID_GOAL` | 400 | Goal 为空 | `POST /api/projects/run` |
| `PROJECT_NOT_FOUND` | 404 | 项目 ID 不存在 | `GET /api/projects/{id}` |
| `PROJECT_RUNNING` | 409 | 项目正在运行中 | `DELETE /api/projects/{id}` |
| `DELIVERABLE_NOT_FOUND` | 404 | 交付物文件不存在 | `GET .../deliverable/{task_id}` |
| `INVALID_PROJECT_ID` | 400 | project_id 含非法字符 | 路径包含 `..`/`/`/`\\` |
| `JOB_NOT_FOUND` | 404 | Job ID 不存在 | `GET /api/jobs/{id}` |
| `INVALID_CHANNEL` | 400 | channel_id 非法 | 路径包含 `..`/`/` |
| `INVALID_MODE` | 400 | mode 参数不合法 | `POST /api/projects/run` |
| `INIT_FAILED` | 500 | 初始化失败 | `POST /api/init` |

---

*本文档基于 `backend/hub/api/server.py` + `observability_api.py` 的当前路由自动生成。新增或修改 API 时请同步更新。*