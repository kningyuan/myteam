# myteam 前端 API 文档

> 来源：前端 `frontend/*.js` 所有 `fetch()` 调用  
> 版本：2026-06-07  
> 说明：从前端角度列出每个页面/功能需要的后端接口

---

## 目录

1. [初始化与状态](#1-初始化与状态)
2. [Dashboard / 首页](#2-dashboard--首页)
3. [Agent 管理](#3-agent-管理)
4. [私聊对话](#4-私聊对话)
5. [群组](#5-群组)
6. [项目（编排内核）](#6-项目编排内核)
7. [可观测性（只读）](#7-可观测性只读)
8. [配置](#8-配置)
9. [Workspace / 频道](#9-workspace--频道)
10. [附录：前端页面 → API 映射](#10-附录前端页面--api-映射)

---

## 1. 初始化与状态

### `POST /api/init`

**用途**：首次使用时的初始化，创建默认 Agent 等工作目录

**输入**：无

**输出**：
```json
{ "message": "初始化完成" }
```

---

### `POST /api/demo`

**用途**：一键创建 Demo 项目并启动内核编排。常用于空态引导

**输入**：无

**输出**：
```json
{ "project_id": "demo-xxx" }
```

> 前端收到后自动切换到 projects tab 并选中该项目

---

### `GET /api/status`

**用途**：检查 Hub 服务状态

**输出**：
```json
{ "status": "ok", "initialized": true }
```

---

## 2. Dashboard / 首页

### `GET /api/obs/summary`

**用途**：Dashboard 统计卡片 + 项目列表

**输入**：无

**输出**：
```json
{
  "totals": { "projects": 5, "running": 2, "tokens": 150000 },
  "projects": [
    {
      "id": "proj-001",
      "title": "项目标题",
      "status": "in_progress",
      "progress": 0.65,
      "task_count": 8,
      "tokens": 35000,
      "budget": 100000,
      "budget_ratio": 0.35,
      "budget_state": "ok"
    }
  ]
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `totals.projects` | int | 项目总数 |
| `totals.running` | int | 运行中数量 |
| `totals.tokens` | int | 全局累计 token |
| `projects[].id` | string | 项目 ID |
| `projects[].title` | string | 标题 |
| `projects[].status` | string | `in_progress` / `completed` / `failed` / `cancelled` 等 |
| `projects[].progress` | float | 0~1 |
| `projects[].budget` | int\|null | token 预算上限 |
| `projects[].budget_ratio` | float | 已用比例 |
| `projects[].budget_state` | string | `ok` / `alert` / `over` |

---

## 3. Agent 管理

### `GET /api/agents`

**用途**：获取所有 Agent 列表（侧栏、管理页）

**输出**：
```json
{
  "agents": [
    {
      "id": "developer",
      "name": "开发者",
      "backend": "opencode",
      "model": "claude-sonnet-4-20250506",
      "workspace": "business/workspaces/workspace-developer/"
    }
  ]
}
```

---

### `POST /api/agents/create`

**用途**：从描述动态创建 Agent

**输入**：
```json
{
  "description": "负责编写和优化 SEO 文章",
  "agent_id": "seo-writer",
  "chinese_name": "SEO 优化师",
  "backend": "opencode",
  "model": "claude-sonnet-4-20250506"
}
```

**输出**：
```json
{
  "agent": {
    "id": "seo-writer",
    "name": "SEO 优化师",
    "backend": "opencode",
    "model": "claude-sonnet-4-20250506",
    "workspace": "business/workspaces/workspace-seo-writer/",
    "files": ["AGENTS.md", "IDENTITY.md", "SOUL.md"]
  }
}
```

---

### `GET /api/agents/suggest-id?description=xxx`

**用途**：根据描述自动推荐 agent_id

**输出**：
```json
{ "suggested_id": "seo-writer" }
```

---

### `POST /api/agents/{agent_id}/config`

**用途**：修改 Agent 的 backend / model（对话页顶栏配置弹窗）

**输入**：
```json
{ "backend": "claude", "model": "claude-sonnet-4-20250506" }
```

**输出**：
```json
{ "success": true, "agent_id": "...", "backend": "claude", "model": "..." }
```

---

### `PUT /api/agents/{agent_id}/manage`

**用途**：管理页的编辑弹窗（修改名称、后端、模型、工作目录）

**输入**：
```json
{ "name": "新名称", "backend": "opencode", "model": "...", "workspace": "..." }
```

**输出**：
```json
{ "success": true }
```

---

### `DELETE /api/agents/{agent_id}`

**用途**：删除 Agent

**输出**：
```json
{ "success": true }
```

---

### `POST /api/agents/apply-model`

**用途**：批量将某个后端下所有 agent 的模型统一修改

**输入**：
```json
{ "backend": "opencode", "model": "claude-sonnet-4-20250506" }
```

**输出**：
```json
{ "applied": ["agent1", "agent2"], "skipped": ["agent3"] }
```

---

### `GET /api/agents/{agent_id}/chats`

**用途**：获取 Agent 的后台私聊消息（轮询用，检测新消息）

**输出**：
```json
{ "messages": [{ "role": "user", "content": "...", "ts": 1700000000000 }] }
```

---

### `GET /api/agents/{agent_id}/events` （SSE）

**用途**：SSE 流，推送 Agent 后台任务事件（thinking / done / error）

**事件格式**：
```
data: {"event": "agent_thinking", "data": {"agent_id": "...", "type": "text", "content": "..."}}
data: {"event": "agent_done", "data": {"agent_id": "...", ...}}
data: {"event": "error", "data": {"message": "..."}}
```

---

## 4. 私聊对话

### `GET /api/chat/{agent_id}/messages`

**用途**：加载对话历史（后端持久化的消息）

**输出**：
```json
{
  "messages": [
    { "role": "user", "text": "你好", "created_at": "2026-06-07T12:00:00" },
    { "role": "agent", "text": "你好！", "created_at": "2026-06-07T12:00:05" }
  ]
}
```

---

### `GET /api/chat/{agent_id}?message=xxx`

**用途**：发送消息给 Agent，返回 SSE 流式响应

**输入**：`message` query param

**响应格式**（SSE）：
```
data: {"event": "thinking", "data": {"type": "text", "content": "正在思考..."}}
data: {"event": "thinking", "data": {"type": "step_start"}}
data: {"event": "thinking", "data": {"type": "tool_use", "name": "Read", "input": {...}}}
data: {"event": "thinking", "data": {"type": "tool_result", "content": "..."}}
data: {"event": "thinking", "data": {"type": "step_finish", "tokens": {"input": 100, "output": 50}}}
data: {"event": "citations", "data": [{"type": "citation", "title": "...", "snippet": "...", "url": "..."}]}
data: {"event": "done", "data": {"session_id": "..."}}
data: [DONE]
```

---

### `POST /api/chat/{agent_id}/clear`

**用途**：清空对话上下文（同时清前端缓存 + 后端 Agent session）

**输出**：
```json
{ "success": true, "message": "对话已清空" }
```

---

### `POST /api/chat/{agent_id}/archive`

**用途**：删除对话（归档到后端，可搜索恢复）

**输入**：
```json
{
  "snapshot": {
    "label": "Agent Name",
    "messages": [{ "role": "user", "content": "...", "thinking": [] }]
  }
}
```

**输出**：
```json
{ "success": true, "message": "...", "snapshot": {...} }
```

---

### `POST /api/chat/{agent_id}/restore`

**用途**：恢复已归档的对话

**输出**：
```json
{ "snapshot": { "messages": [...] } }
```

---

### `GET /api/chat/archives/search?q=xxx`

**用途**：搜索已归档的对话

**输出**：
```json
{ "results": [{ "agent_id": "seo-writer", "label": "SEO 优化师" }] }
```

---

## 5. 群组

### `GET /api/groups`

**用途**：群组列表

**输出**：
```json
{
  "groups": [
    {
      "id": "group-001",
      "name": "开发团队",
      "status": "active",
      "member_count": 4,
      "project_id": "proj-001",
      "last_message_at": 1700000000,
      "created_at": 1700000000
    }
  ]
}
```

---

### `POST /api/groups`

**用途**：创建群组

**输入**：
```json
{ "name": "开发团队", "description": "开发讨论群" }
```

**输出**：
```json
{ "success": true, "group_id": "group-001", "message": "群组已创建" }
```

---

### `GET /api/groups/{group_id}`

**用途**：群组详情（含成员列表和消息历史）

**输出**：
```json
{
  "group": {
    "id": "group-001",
    "name": "开发团队",
    "members": ["main", "developer"],
    "project_id": "proj-001",
    "messages": [
      { "sender": "user", "text": "大家好", "timestamp": 1700000000 },
      { "sender": "developer", "text": "收到", "timestamp": 1700000005 }
    ]
  }
}
```

---

### `GET /api/groups/{group_id}/chat?sender=user&text=xxx`

**用途**：发群消息，返回 SSE 流

**输入**：`sender` + `text` query params

**SSE 事件**：
```
data: {"event": "routing", "data": {"to": "developer"}}
data: {"event": "agent_thinking", "data": {"agent_id": "developer", "type": "text", "content": "..."}}
data: {"event": "group_message", "data": {"sender": "developer", "text": "回复内容"}}
data: {"event": "agent_done", "data": {"agent_id": "developer"}}
data: [DONE]
```

---

### `POST /api/groups/{group_id}/members`

**用途**：添加成员

**输入**：
```json
{ "agent_id": "developer" }
```

---

### `DELETE /api/groups/{group_id}/members/{agent_id}`

**用途**：移除成员

---

### `POST /api/groups/{group_id}/dissolve`

**用途**：解散群组

---

### `POST /api/groups/{group_id}/restore`

**用途**：恢复已解散群组

---

### `POST /api/groups/{group_id}/clear`

**用途**：清空群聊消息

---

### `GET /api/groups/search?q=xxx&include_dissolved=true`

**用途**：搜索群组（含已解散）

**输出**：
```json
{ "groups": [{ "id": "...", "name": "...", "status": "dissolved", "member_count": 3 }] }
```

---

### `GET /api/groups/{group_id}/events` （SSE）

**用途**：群组实时事件流（新消息通知）

---

## 6. 项目（编排内核）

### `POST /api/projects/run`

**用途**：发起一个新项目，启动编排内核

**输入**：
```json
{
  "goal": "为 example.com 做一次 SEO 评估",
  "title": "SEO 评估项目",
  "mode": "one_shot",
  "budget": 150000,
  "review": true
}
```

**输出**：
```json
{ "project_id": "proj-001", "success": true }
```

---

### `GET /api/projects/run-status/{project_id}`

**用途**：检查内核进程运行状态

**输出**：
```json
{ "running": true, "error": "" }
```

---

### `POST /api/projects/{project_id}/cancel`

**用途**：取消项目（当前任务跑完后不再派发）

---

### `POST /api/projects/{project_id}/resume`

**用途**：断点续跑

**输出**：
```json
{ "resumed": true, "reason": "" }
```

---

### `DELETE /api/projects/{project_id}`

**用途**：彻底删除项目（数据库 + 交付物目录 + Agent 临时文件）

---

## 7. 可观测性（只读）

### `GET /api/obs/projects`

**用途**：项目列表（含进度）

**输出**：
```json
{
  "projects": [
    {
      "id": "proj-001", "title": "项目标题",
      "status": "in_progress", "progress": 0.65,
      "task_count": 8, "mode": "one_shot",
      "updated_at": "2026-06-07T12:00:00"
    }
  ]
}
```

---

### `GET /api/obs/projects/{project_id}/overview`

**用途**：项目概览（任务列表 + 进度 + 预算）

**输出**：
```json
{
  "title": "项目标题",
  "status": "in_progress",
  "progress": 0.65,
  "budget": 150000,
  "budget_ratio": 0.35,
  "budget_state": "ok",
  "tokens": 35000,
  "tasks": [
    {
      "id": "t1",
      "name": "任务名称",
      "status": "completed",
      "agent": "main",
      "dependencies": [],
      "summary": "任务摘要"
    }
  ]
}
```

---

### `GET /api/obs/projects/{project_id}/cost`

**用途**：成本明细（按 Agent / 按 Task）

**输出**：
```json
{
  "project": 35000,
  "by_agent": { "main": 10000, "researcher": 15000, "developer": 10000 },
  "by_task": { "t1": 10000, "t2": 15000, "t3": 10000 }
}
```

---

### `GET /api/obs/projects/{project_id}/fleet`

**用途**：舰队状态（各 Agent 当前生命周期）

**输出**：
```json
{ "fleet": { "main": "running", "researcher": "done", "developer": "stuck" } }
```

---

### `GET /api/obs/projects/{project_id}/events`

**用途**：执行事件列表（执行树 + 时间线）

**输出**：
```json
{
  "events": [
    {
      "ts": "2026-06-07T11:29:01",
      "category": "interaction",
      "kind": "team_config",
      "agent_id": "main",
      "task_id": "",
      "interaction_id": "proj-001:team_config",
      "status": "done",
      "attempt": 1,
      "tokens": 500
    },
    {
      "ts": "2026-06-07T11:29:05",
      "category": "event",
      "kind": "gate_passed",
      "payload": { "failures": [] }
    }
  ]
}
```

**`category` 说明**：

| `category` | 含义 |
|------------|------|
| `interaction` | 交互节点（可折叠展开） |
| `event` | 事件节点（独立显示） |

**`kind` 枚举**（`interaction`）：`team_config` / `task_plan` / `execute` / `review` / `triage`

**`kind` 枚举**（`event`）：`gate_passed` / `gate_failed` / `review_done` / `review_unreachable` / `plan_rejected` / `blocked` / `budget_alert` / `budget_over` / `cycle_done` / `watchdog_soft_idle` / `watchdog_hard_kill` / `transport_error` / `reconcile_timed_out` / `reconcile_adopted` / `tool_use` / `tool_result` / `prompt_sent` / `request_snapshot` / `response_snapshot` / `message`

---

### `GET /api/obs/projects/{project_id}/stream` （SSE）

**用途**：项目实时流（SSE），数据变化时推送 tick

**事件格式**：
```
data: {"event": "project_updated"}
data: [DONE]
```

---

### `GET /api/obs/interactions/{interaction_id}/timeline`

**用途**：单个交互节点的详细时间线（skill 调用链）

**输出**：
```json
{
  "timeline": [
    { "seq": 1, "kind": "tool_use", "payload": { "name": "Read", "input": {...}, "output": "..." } },
    { "seq": 2, "kind": "step_finish", "payload": { "tokens": { "input": 100, "output": 50 } } }
  ]
}
```

---

### `GET /api/obs/interactions/{interaction_id}/events` （SSE）

**用途**：交互节点实时事件流

---

### `GET /api/projects/{project_id}/deliverable/{task_id}`

**用途**：获取某任务的交付物清单

**输出**：
```json
{
  "task_type": "artifact",
  "base": "deliverables/*.md",
  "primary": { "path": "output/report.md", "exists": true },
  "files": [
    { "path": "output/report.md", "name": "report.md", "kind": "doc", "location": "workspace" },
    { "path": "output/data.json", "name": "data.json", "kind": "data", "location": "legacy" }
  ],
  "content": "# 报告正文..."
}
```

---

### `GET /api/projects/{project_id}/deliverable/{task_id}/file?path=xxx`

**用途**：读取交付物具体文件内容

**输出**：
```json
{ "path": "output/report.md", "content": "# 正文...", "kind": "doc", "exists": true }
```

---

### `GET /api/obs/task-types`

**用途**：任务类型注册表（管理页「任务类型」表格）

**输出**：
```json
{
  "task_types": [
    {
      "task_type": "artifact",
      "outcome_kind": "artifact",
      "required_sections": ["目标", "方法"],
      "sections": [{ "name": "目标", "description": "..." }],
      "structure": [],
      "gate_checks": ["须含「目标」", "须含「方法」"]
    }
  ]
}
```

---

### `GET /api/obs/memory?project_id=xxx`

**用途**：知识库条目列表

**输出**：
```json
{
  "memory": [{ "id": 1, "project_id": "proj-001", "title": "xxx", "tags": ["seo"], "preview": "..." }],
  "total": 50
}
```

---

## 8. 配置

### `GET /api/config`

**用途**：读取系统配置

**输出**：
```json
{
  "config": {
    "system": {
      "port": 8765, "default_backend": "opencode", "default_model": "...",
      "debug": false, "audit_log": false, "price_per_mtok": 0,
      "default_review": false
    },
    "backends": {
      "opencode": { "cli_path": "", "model_aliases": {} }
    },
    "models": {
      "opencode": [{ "id": "model-id", "name": "显示名", "provider": "anthropic", "default": true }]
    }
  }
}
```

---

### `PUT /api/config`

**用途**：保存系统配置

**输入**：与 GET 输出结构相同

**输出**：
```json
{ "success": true, "config": {...} }
```

---

### `GET /api/skill-config`

**用途**：读取协作引擎配置

**输出**：
```json
{
  "config": {
    "notifications": { "use_project_group": true },
    "hub": { "url": "http://127.0.0.1:8765" },
    "executor": { "poll_interval": 5, "ack_timeout": 300, ... },
    "auto_group": { "enabled": true }
  }
}
```

---

### `PUT /api/skill-config`

**用途**：保存协作引擎配置

---

### `GET /api/backends`

**用途**：获取可用 CLI 后端及其模型列表

**输出**：
```json
{
  "backends": [
    {
      "id": "opencode", "name": "OpenCode",
      "models": [
        { "id": "claude-sonnet-4-20250506", "name": "Claude Sonnet 4", "provider": "anthropic", "default": true }
      ]
    }
  ]
}
```

---

## 9. Workspace / 频道

### `GET /api/workspace/events?project_id=xxx&type=xxx&limit=50`

**用途**：WorkspaceEvent 列表（R2 事件溯源）

**输出**：
```json
{
  "events": [
    {
      "id": "...", "project_id": "proj-001",
      "type": "project.task.updated",
      "timestamp": "2026-06-07T12:00:00",
      "source": "kernel",
      "payload": { "status": "completed" },
      "metadata": { "task_id": "t1" }
    }
  ]
}
```

---

### `GET /api/workspace/events/stream` （SSE）

**用途**：WorkspaceEvent 实时 SSE 流

### `GET /api/workspace/channels`

**用途**：频道列表

### `POST /api/workspace/channels`

**用途**：创建频道

### `GET /api/workspace/channels/{channel_id}/messages`

**用途**：频道消息历史

### `POST /api/workspace/channels/{channel_id}/messages`

**用途**：发送频道消息

---

## 10. 附录：前端页面 → API 映射

| 前端页面 | 使用的主要 API |
|----------|----------------|
| **Dashboard**（首页） | `GET /api/obs/summary`, `POST /api/init`, `POST /api/demo` |
| **对话**（私聊） | `GET /api/agents`, `GET /api/chat/{id}/messages`, `GET /api/chat/{id}?message=`, `POST /api/chat/{id}/clear`, `POST /api/chat/{id}/archive`, `POST /api/chat/{id}/restore`, `GET /api/chat/archives/search`, `GET /api/agents/{id}/events` |
| **群组** | `GET /api/groups`, `POST /api/groups`, `GET /api/groups/{id}`, `GET /api/groups/{id}/chat`, `GET /api/groups/{id}/events`, `GET /api/groups/search`, 成员管理 |
| **项目详情→概览** | `GET /api/obs/projects/{id}/overview`, `GET /api/obs/projects/{id}/cost`, `GET /api/obs/projects/{id}/fleet`, `GET /api/projects/run-status/{id}`, `GET /api/obs/projects/{id}/events` |
| **项目详情→DAG** | `GET /api/obs/projects/{id}/overview`（提取 tasks） |
| **项目详情→执行过程** | `GET /api/obs/projects/{id}/events`, `GET /api/obs/interactions/{iid}/timeline`, `GET /api/obs/interactions/{iid}/events` |
| **项目详情→交付物** | `GET /api/projects/{id}/deliverable/{task_id}`, `GET /api/projects/{id}/deliverable/{task_id}/file?path=` |
| **项目详情→时间线** | `GET /api/obs/projects/{id}/events`（前端适配为 timeline 格式） |
| **项目详情→成本** | `GET /api/obs/projects/{id}/cost` |
| **项目操作** | `POST /api/projects/run`, `POST /api/projects/{id}/cancel`, `POST /api/projects/{id}/resume`, `DELETE /api/projects/{id}` |
| **管理→Agent** | `GET /api/agents`, `POST /api/agents/create`, `PUT /api/agents/{id}/manage`, `DELETE /api/agents/{id}`, `POST /api/agents/apply-model`, `GET /api/agents/suggest-id` |
| **管理→任务类型** | `GET /api/obs/task-types` |
| **管理→知识库** | `GET /api/obs/memory` |
| **设置** | `GET /api/config`, `PUT /api/config`, `GET /api/skill-config`, `PUT /api/skill-config`, `GET /api/backends` |
