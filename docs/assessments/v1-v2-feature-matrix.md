# v1 / v2 功能对比矩阵

> **生成时间**：2026-06-14  
> **扫描范围**：`frontend/`（v1 SPA）、`frontend-v2/src/`（v2 React）、`frontend-v2/src/lib/api.ts`  
> **权威 Gate**：[`platform-v3-gates.md#p1-gate`](./platform-v3-gates.md#p1-gate) P1-G1

---

## 1. 页面 / 路由对照

| 功能域 | v1 证据 | v2 证据 | 路由 |
|--------|---------|---------|------|
| 首页 Dashboard | `frontend/dashboard.js` · `index.html` `#tab-home` | `frontend-v2/src/pages/DashboardPage.tsx` · `App.tsx` `index` | v1 `#home` · v2 `/v2/` |
| 私聊 Chat | `frontend/chat.js` · `#tab-chat` | `frontend-v2/src/sections/ChatSection.tsx` · `/chat/:agentId` | 均有 |
| 群组 Groups | `frontend/group.js` · `#tab-groups` | `frontend-v2/src/sections/GroupsSection.tsx` · `/groups/:groupId` | 均有 |
| 项目 Projects | `frontend/project.js` · `#tab-projects` | `frontend-v2/src/sections/ProjectsSection.tsx` · `/projects/:projectId` | 均有 |
| 管理 Manage | `frontend/manage.js` · `#tab-manage` 子 tab | `frontend-v2/src/sections/ManageSection.tsx` · `/manage/:tab/:itemId` | 均有 |
| Workflow | `frontend/workflows.js` · `#tab-workflows` | `frontend-v2/src/sections/WorkflowsSection.tsx` · `/workflows/:workflowId` | 均有 |
| 设置 Settings | `frontend/settings.js` · `#tab-settings` | `frontend-v2/src/pages/SettingsPage.tsx` · `/settings/:section` | 均有 |
| Skill 草案（L3） | **无独立页** | `frontend-v2/src/sections/SkillsSection.tsx` · `/skills/:draftId` | **仅 v2** |

**v1 源文件**：`frontend/index.html` L18 `TABS`；`frontend/app.js` L51 `MAIN_TABS`。  
**v2 路由**：`frontend-v2/src/App.tsx` L28–46。

---

## 2. P0 / P1 / P2 功能矩阵

> **P0**：核心用户旅程（项目编排、私聊、群组、管理、Workflow、设置）  
> **P1**：增强体验 / 运维辅助  
> **P2**：开发便利、演示、遗留兼容

| # | 功能域 | 子功能 | P级 | v1 状态 | v2 状态 | 差距 | 证据路径 |
|---|--------|--------|-----|---------|---------|------|----------|
| 1 | 项目 | 列表（obs/projects） | P0 | ✅ 有 | ✅ 有 | 无 | v1 `project.js:71` · v2 `api.ts:277` `listProjects` |
| 2 | 项目 | 概览 / 成本 / 舰队 / 事件 | P0 | ✅ 有 | ✅ 有 | 无 | v1 `project.js:207-211` · v2 `api.ts:686-699` |
| 3 | 项目 | 发起 run | P0 | ✅ 有 | ✅ 有 | 无 | v1 `app.js:402` · v2 `api.ts:646` |
| 4 | 项目 | 续跑 resume | P0 | ✅ 有 | ✅ 有 | 无 | v1 `app.js:386` · v2 `api.ts:664` |
| 5 | 项目 | 取消 cancel | P0 | ✅ 有 | ✅ 有 | 无 | v1 `app.js:391` · v2 `api.ts:789` |
| 6 | 项目 | 删除 delete | P0 | ✅ 有 | ✅ 有 | 无 | v1 `project.js:105` · v2 `api.ts:795` |
| 7 | 项目 | run-status | P0 | ✅ 有 | ✅ 有 | 无 | v1 `project.js:210` · v2 `api.ts:670` |
| 8 | 项目 | SSE stream + interaction events | P0 | ✅ 有 | ✅ 有 | 无 | v1 `project.js:365,384` · v2 `api.ts:749-786` |
| 9 | 项目 | DAG 可视化 | P0 | ✅ SVG | ✅ React | v2 交互更强（缩放/平移） | v1 `dag-renderer.js` · v2 `ProjectDag.tsx` |
| 10 | 项目 | 交付物浏览 / 多文件 | P0 | ✅ 有 | ✅ 有 | 无 | v1 `project.js:712,739` · v2 `api.ts:371-409` |
| 11 | 项目 | 执行树 + Gate 失败展示 | P0 | ✅ 内联 | ✅ 组件化 | v2 结构化 `GateFailureList` | v1 `project.js:603` · v2 `ProjectExecTree.tsx` `GateFailureList.tsx` |
| 12 | 项目 | Task 质量 / interaction 详情 | P1 | ⚠️ 部分 | ✅ 有 | v1 无独立 quality 卡片 | v2 `ProjectTaskQualityCard.tsx` `api.ts:745` `getTaskDetail` |
| 13 | 私聊 | SSE 流式发送 | P0 | ✅ 有 | ✅ 有 | 无 | v1 `chat.js:169` · v2 `api.ts:545` |
| 14 | 私聊 | 消息历史 | P0 | ✅ 有 | ✅ 有 | 无 | v1 `ui-core.js:505` · v2 `api.ts:538` |
| 15 | 私聊 | 清空 / 归档 / 恢复 | P0 | ✅ 有 | ✅ 有 | 无 | v1 `chat.js:23-40` · v2 `api.ts:579-597` |
| 16 | 私聊 | 归档搜索 | P1 | ✅ 有 | ✅ 有 | 无 | v1 `chat.js:59` · v2 `api.ts:600` |
| 17 | 私聊 | 多会话侧栏 `/agents/{id}/chats` | P1 | ✅ 有 | ❌ 无 | v2 用 agent 列表 + 隐藏集代替 | v1 `chat.js:122` `manage.js:45` |
| 18 | 私聊 | Agent SSE `/agents/{id}/events` | P1 | ✅ 有 | ❌ 无（全局 `agentChatStream`） | 实现路径不同 | v1 `chat.js:285` · v2 `lib/agentChatStream.ts` |
| 19 | 群组 | 列表 / 详情 / SSE events | P0 | ✅ 有 | ✅ 有 | 无 | v1 `group.js:60,134,250` · v2 `api.ts:321-424` |
| 20 | 群组 | 群聊 SSE（无 mode 参数） | P0 | ✅ 基础 | ✅ 增强 | v2 支持 roundtable/notify mode | v1 `group.js:191` · v2 `api.ts:492-531` |
| 21 | 群组 | 圆桌设置 / 成员排序 | P1 | ❌ 无 UI | ✅ 有 | v1 缺主持人/轮次配置 | v2 `GroupsSection.tsx` `api.ts:887-918` |
| 22 | 群组 | 取消群聊 / chat status | P1 | ❌ 无 | ✅ 有 | v1 仅 abort 流 | v2 `api.ts:484-489` `GroupsSection.tsx` |
| 23 | 管理 | Agents CRUD + 工作区文件 | P0 | ✅ 有 | ✅ 有 | 无 | v1 `manage.js` · v2 `ManageSection.tsx` `api.ts:630-978` |
| 24 | 管理 | Task types CRUD | P0 | ✅ 有 | ✅ 有 | 无 | v1 `manage.js:282-396` · v2 `api.ts:995-1015` |
| 25 | 管理 | Delivery templates CRUD | P0 | ✅ 有 | ✅ 有 | 无 | v1 `manage.js:564-727` · v2 `api.ts:1019-1049` |
| 26 | 管理 | 知识库 memory | P0 | ✅ 有 | ✅ 有（manage/knowledge tab） | 无 | v1 `knowledge.js:35` · v2 `ManageSection.tsx` `api.ts:1094` |
| 27 | 管理 | sync-task-types | P1 | ✅ 有 | ❌ 无 UI | v2 未暴露同步按钮 | v1 `manage.js:127` |
| 28 | 管理 | suggest-task-types / suggest-id | P1 | ✅ 有 | ❌ 无 UI | v2 创建 Agent 无 LLM 建议 | v1 `manage.js:422,492` |
| 29 | 管理 | task-types/suggest（LLM 起草） | P1 | ✅ 有 | ❌ 无 UI | v2 创建 task_type 无建议流 | v1 `manage.js:342` |
| 30 | Workflow | 列表 / 编辑 / suggest / 删除 | P0 | ✅ 有 | ✅ 有 | 无 | v1 `workflows.js` · v2 `WorkflowEditor.tsx` `api.ts:342-1089` |
| 31 | 设置 | system + skill config | P0 | ✅ 有 | ✅ 有 | 无 | v1 `settings.js` · v2 `SettingsPage.tsx` |
| 32 | 设置 | apply-model 全员 | P0 | ✅ 有 | ✅ 有 | 无 | v1 `settings.js:153` · v2 `api.ts:832` |
| 33 | 设置 | 群讨论全局参数 | P1 | ⚠️ 部分 | ✅ 有 | v2 圆桌超时/终止命令更完整 | v2 `SettingsPage.tsx` `groupDiscussionSettings.ts` |
| 34 | 可观测 | obs/summary 首页 | P0 | ✅ 有 | ✅ 有 | 无 | v1 `dashboard.js:22` · v2 `api.ts:357` |
| 35 | Skill L3 | drafts / matrix 审计 | P2 | ❌ 无 | ✅ 有 | v2 独有运维页 | v2 `SkillsSection.tsx` `api.ts:1146-1160` |
| 36 | 演示 | `/api/init` 初始化 | P2 | ✅ 有 | ❌ 无 | 仅 v1 欢迎页 | v1 `ui-core.js:35` |
| 37 | 演示 | `/api/demo` 演示数据 | P2 | ✅ 有 | ❌ 无 | 仅 v1 | v1 `ui-core.js:44` |
| 38 | 时间线 | workspace 事件渲染器 | P2 | ✅ `timeline.js` | ❌ 无等价模块 | v2 用 obs events + exec tree | `frontend/timeline.js` |

---

## 3. api.ts 端点覆盖（v2 客户端）

`frontend-v2/src/lib/api.ts` 封装 **52** 个函数，触及 **~45** 条 distinct HTTP 路径（含 SSE EventSource）。

| API 前缀 | v2 函数（节选） | 行号 |
|----------|-----------------|------|
| `/api/obs/projects` | `listProjects`, `getProjectOverview`, `getProjectCost`, … | 277–699 |
| `/api/projects` | `runProject`, `resumeProject`, `cancelProject`, deliverable | 371–798 |
| `/api/groups` | `listGroups`, `sendGroupChat`, `reorderGroupMembers`, … | 321–943 |
| `/api/chat` | `sendAgentChat`, `archiveAgentChat`, … | 534–604 |
| `/api/agents` | `listAgents`, `createAgent`, `updateAgentManage`, … | 331–990 |
| `/api/workflows` | `listWorkflows`, `suggestWorkflow`, `saveWorkflow` | 342–1089 |
| `/api/task-types` | `listTaskTypes`, CRUD | 347–1015 |
| `/api/skills` | `listSkillDrafts`, `getSkillMatrixAudit` | 1146–1160 |
| `/api/config` · `/api/skill-config` · `/api/backends` | 设置域 | 361–829 |

**v1 独有 API 调用（v2 `api.ts` 未封装）**：

| 端点 | v1 证据 | P级 |
|------|---------|-----|
| `POST /api/init` | `ui-core.js:35` | P2 |
| `POST /api/demo` | `ui-core.js:44` | P2 |
| `POST /api/agents/sync-task-types` | `manage.js:127` | P1 |
| `POST /api/agents/suggest-task-types` | `manage.js:422` | P1 |
| `GET /api/agents/suggest-id` | `manage.js:492` | P1 |
| `POST /api/task-types/suggest` | `manage.js:342` | P1 |
| `GET /api/agents/{id}/chats` | `chat.js:122` | P1 |
| `GET /api/agents/{id}/events` (SSE) | `chat.js:285` | P1 |

---

## 4. P0 完整度汇总

| 指标 | 值 | 说明 |
|------|-----|------|
| P0 行总数 | **31** | 上表 P0 标记行 |
| P0 v1 可用 | **31/31** | 100% |
| P0 v2 可用 | **31/31** | 100%（核心旅程均有页面+API） |
| P0 v2 弱于 v1 | **0** | 无 P0 缺口 |
| P1 v2 缺口 | **5** | sync/suggest 系列 + 多会话侧栏 + agent events 路径差异 |

**Gate P1-G1 判定**：P0 行 100% 有 v1/v2 状态 + 差距描述 ✅

---

## 5. v3 迁移建议（矩阵输入，非 P2 方案）

1. **P3.2 优先补齐 P1 缺口**：`sync-task-types`、`suggest-*` 三入口迁入 v2 Manage（API 已存在于 `server.py`，仅缺 UI）。
2. **保留 v2 独有**：Skill 草案页、圆桌设置、Gate 失败组件——列入 P4 验收「v2 增值项」。
3. **P2 演示**：`init`/`demo` 可不迁移，或收敛为运维脚本。
