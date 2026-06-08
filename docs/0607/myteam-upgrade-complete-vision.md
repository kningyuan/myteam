# myteam 升级完成全景描述

> **文档类型**：产品愿景 / 能力全景 / 验收蓝图  
> **编写日期**：2026-06-06  
> **上游输入**：product-assessment-report / system-assessment-report / user-perspective-product-analysis / ui-design-assessment / metagpt-comparison / OPENAGENTS-checklist / product-improvement-plan / myteam-upgrade-requirements  
> **受众**：研发 agent、设计 agent、项目决策者  
> **用途**：回答「升级完毕后 myteam 是什么样子」——不描述怎么做，只描述做成什么样  
> **状态**：**已归档** — 内容已合并至 [`myteam-upgrade-comprehensive-plan.md`](./myteam-upgrade-comprehensive-plan.md) 上篇（§1–§8）

> ⚠️ **请勿再以本文档为执行依据。** 终态描述与分阶段需求见 [`myteam-upgrade-comprehensive-plan.md`](./myteam-upgrade-comprehensive-plan.md)。

---

## 1. 一句话定位

**myteam 是一个可长期运行、可追踪、可协作的 Agent Team Workspace**——用户打开浏览器即可创建项目、编排多 Agent 协作、实时追踪 DAG 执行进度、浏览交付物、复盘完整时间线；编排内核通过 Interaction 契约 + Plan Gate + 确定性校验保证执行质量。

---

## 2. 升级完成后的用户感知

### 2.1 用户类型与感受

| 用户类型 | 升级后感受 |
|----------|------------|
| **独立开发者 / 技术用户** | 一个 Workspace 搞定聊天+编排+交付，Hub 是主入口，CLI 是高级入口。5 分钟初始化并跑通 Demo，30 分钟搭建自己的多 Agent 项目 |
| **产品 / 业务用户** | 不需要打开终端。浏览器内填 Goal、选模式、看 DAG 进度、读交付物。失败了有中文原因+建议操作，不需要找研发 |
| **团队管理者** | 项目列表一目了然，能看到每个项目的状态、成本、耗时、Agent 利用率。历史可回溯，多个项目可对比 |

### 2.2 从「打开浏览器」到「拿到交付物」的完整旅程

```
首次打开 Hub
  │
  ├─ 检测到未初始化
  │   └─ Home 空态引导：「初始化 Agent」→「运行 Demo」
  │       └─ Demo 自动完成 → 进入项目频道 → 看到完整执行记录 + 交付物
  │
  ├─ 已初始化，无项目
  │   └─ Home 仪表盘：统计卡片（项目数/运行中/Token/成本）+「创建项目」按钮
  │       └─ 创建项目：填 Goal、选模式（one_shot/recurring）、设 Budget、可选 Backend
  │
  ├─ 创建项目后
  │   └─ Supervisor 启动 Kernel Job → 自动跳转项目工作台
  │       ├─ 概览页：进度条、Fleet 摘要、快捷操作（取消/重试）
  │       ├─ DAG 图：SVG 拓扑、节点着色（运行中/完成/失败/阻塞）、点击看任务详情
  │       ├─ 执行树：交互式层级、紧凑/展开切换、状态过滤
  │       ├─ 交付物：文件树 + Markdown/文本预览 + 下载 + 最终交付标记
  │       ├─ 成本：柱状图+饼图+预算告警
  │       └─ 时间线：统一 WorkspaceEvent 视图
  │
  ├─ 运行中
  │   └─ 项目频道自动推送：task 状态 / Gate 结果 / deliverable 就绪 / triage / 预算事件
  │       └─ 支持 thread 讨论、@mention 指定 Agent
  │
  └─ 完成后
      └─ 交付物可预览/下载/标记最终版本 → 导出摘要 → 创建下一个项目
```

### 2.3 关键指标（升级后）

| 指标 | 升级后值 | 对比升级前 |
|------|----------|------------|
| 新用户首次跑通 | **Hub <5 分钟**（无终端） | CLI 30-60 分钟 |
| 自助排查成功率 | **>75%**（Hub 含排查链接） | ~0%（靠读源码） |
| 跑完到看见交付物 | **Hub 即时浏览+预览+下载** | 需翻文件系统 |
| 编排卖点可感知 | **DAG 图 + 进度条 + 时间线** | 列表为主 |
| 测试回归 | **CI 全绿 <60s** | 全量 pytest 挂起 |
| Hub 独立完成项目 | **创建+启动+频道协作全闭环** | 不能独立完成 |

---

## 3. 升级后的页面与信息架构

### 3.1 全局导航

6 个一级 Tab，一级 Tab 为**全局上下文切换**，二级导航用于**深度内容**：

```
[Home] [Chat] [Groups] [Projects] [Agents] [Settings]
```

### 3.2 Home — 仪表盘与 Onboarding

**空态（首次使用，无项目）**：
- 居中插图 + 文案：「欢迎使用 myteam Agent Team Workspace」
- 三按钮：**初始化 Agent** / **运行 Demo** / **创建项目**
- 底部链接：快速开始文档（Hub 内嵌）

**常态（有项目历史）**：
- 顶部统计行：项目总数、运行中、本月 Token、累计成本——每个数字附带趋势微标（↑↓）
- 项目网格卡片：项目名 / 状态色标 / 最近活动时间 / 快捷入口
- 右侧快捷操作：「新建项目」「运行 Demo」「查看全部项目」

### 3.3 Chat — 单 Agent 对话

- 左侧：Agent 列表（头像 / 名称 / 在线状态 / 当前任务）
- 中间主区域：消息流
  - 三栏结构：角色头像+色带 | 时间戳 | 消息内容
  - 轮次分割线：显示轮次序号、Token 消耗、耗时
  - Thinking 块：可折叠、行号锚点
  - 引用卡片：紧凑行内式（类似 GitHub）
  - 上下文用量指示器
- 底部：输入框 + 模型选择 + 附件上传

### 3.4 Groups — 群组协作

- 左侧：群组列表（名称 / 成员数 / 未读）
- 中间：消息流（同 Chat 结构）
  - 群聊特有：每条消息显示发言人姓名色带 + 头像
  - @mention 输入时弹出候选面板（类似 Slack/Discord）
- 右侧（可选）：成员列表 + 快捷设置入口

### 3.5 Projects — 项目工作台（核心卖点）

二级导航 + 面包屑：`Projects > {项目名} > [概览 | DAG | 执行 | 交付 | 成本 | 时间线]`

#### 概览
- 项目状态徽章（running / completed / failed / cancelled）
- 整体进度条（任务完成数/总数）
- 基本信息：Goal、Mode、Budget、Backend、创建时间
- Fleet 摘要：参与 Agent 列表 + 各状态计数
- 快捷操作：取消运行 / 重试 / 删除项目

#### DAG 图（核心差异化卖点）
- SVG/Canvas 拓扑图：任务节点 + 依赖边
- 节点着色：completed（绿）/ running（蓝）/ failed（红）/ blocked（灰）/ pending（淡蓝）
- 点击节点 → 弹出任务详情抽屉（状态 / Agent / Token / 耗时 / 交付物 / 错误信息）
- 支持缩放和平移
- 图例说明

#### 执行
- 交互式任务树：层级缩进 + 展开/折叠
- 紧凑模式 / 展开模式切换
- 按状态过滤：全部 / 运行中 / 已完成 / 失败 / 阻塞
- SSE 实时更新，新事件 2 秒淡黄色高亮动画
- 每行显示：任务 ID / Agent / task_type / 状态色标 / Token / 耗时

#### 交付物
- 左侧：文件树（按 task 分组）
- 右侧：预览面板
  - Markdown 渲染
  - 纯文本预览
  - 下载按钮
  - 标记「最终交付」按钮
  - 版本对比（同一文件多版本时）
- 项目级聚合交付物列表

#### 成本
- 数据表格：Task / Agent / Token 输入 / Token 输出 / 总 Token / 成本
- 柱状图（按 Agent 分组）：每个 Agent 的 Token 消耗
- 饼图：各 Agent Token 占比
- 预算告警条：已用 / 总预算，接近 80% 时变黄、超预算变红

#### 时间线（统一 WorkspaceEvent）
- 时间线视图：合并 Chat / Task / Gate / Deliverable / Triage / Budget 事件
- 格式：时间戳 + 事件类型徽章 + 摘要 + 详情链接
- SSE 增量推送，新事件 2 秒高亮
- 过滤：按事件类型、按 Agent、按时间范围

### 3.6 Agents — Agent 管理

- 卡片视图（可切换表格视图）：
  - Agent 头像/名称
  - Backend + Model
  - 能力标签（task_type 列表）
  - Workspace 状态（正常 / 缺失 / 错误）
  - Runtime 状态（idle / busy / error）
  - 当前任务（如有）
- 点击 → 抽屉详情：完整配置 + 编辑 + 保存/取消
- 列可隐藏（表格模式下）
- 小屏不横滚

### 3.7 Settings — 系统设置

- Accordion 分组折叠：
  - **系统配置**：端口、默认 Backend、模型列表
  - **Agent 配置**：注册表、Workspace 路径
  - **CLI 配置**：opencode/claude 路径与登录状态检测
  - **网络**：绑定地址、鉴权 Token
  - **关于**：版本、API 文档链接、术语说明
- CLI 与 Hub 配置关系说明内嵌

### 3.8 项目频道（R2 新增，贯穿整体）

- 项目启动时自动创建 `channel/project-{project_id}`
- 在 Projects 上下文或 Groups 下均可进入
- 事件自动流入：
  - task 状态变更
  - Gate 结果
  - deliverable 就绪
  - triage 请求
  - 预算超限
- 支持 thread：任务讨论、review 挂线程
- @mention 可指定 Agent 响应

---

## 4. 升级后的核心能力

### 4.1 编排内核（保持不变——已是核心资产）

| 能力 | 说明 |
|------|------|
| 确定性 DAG 执行 | Kahn 拓扑排序 + 串行节点推进 |
| Plan Gate | agent∈team、task_type 注册表、扇出上限 |
| Interaction 契约 | 6 kind 判别联合体，submit_result 本地校验 |
| 断点续跑 | 崩溃后 workspace GC + 残骸恢复 |
| 适配器隔离 | RunRequest / AgentEvent 唯一跨 CLI 数据合约 |
| 三层分离 | System Kernel / Strategy Registry / Skill Pack |

### 4.2 内核增量增强

| 能力 | 描述 |
|------|------|
| Interaction 内部结构化阶段 | execute/review 提示词含收集→产出→自检三段引导 |
| 运行时递归展开 | needs_review 且范围过大时原地展开子 DAG（深度上限 3） |
| 有限并行（可选） | 独立子 DAG 分支可并发，Store 锁语义清晰后评估 |

### 4.3 Hub / Workspace 层（升级新增）

| 能力 | 描述 |
|------|------|
| **WorkspaceEvent 模型** | 统一事件：chat / task / gate / deliverable / resource / agent status；可查询、可 SSE、可投影 |
| **频道 / 线程** | direct/{agent} / channel/general / channel/project-{id} + thread_id + @mention |
| **Job Supervisor** | job 表持久化；启动/取消/崩溃标记；Hub 重启可查询 |
| **资源索引** | file / context / skill / tool 统一元数据；prompt 可引用地址 |
| **Manifest** | `/.well-known/myteam.json` 暴露只读能力清单 |
| **事件处理链** | persistence → notification(SSE) → projection → audit |
| **友好错误** | 错误码 + 中文文案 + troubleshooting 链接贯穿所有 API |

### 4.4 工程保障（升级新增）

| 能力 | 规格 |
|------|------|
| CI 门禁 | pytest backend <60s 全绿，PR/提交自动运行 |
| 模块化前端 | JS 按 tab 拆 6 文件、CSS 拆 4 文件 |
| 可测试 API | 每个 router 至少 smoke test |
| 可选鉴权 | MYTEAM_API_TOKEN + Bearer header |
| 默认安全 | bind 127.0.0.1；0.0.0.0 opt-in 含警告 |

---

## 5. 升级完成后的数据模型

### 5.1 WorkspaceEvent

```json
{
  "id": "evt_xxxx",
  "type": "project.task.updated",
  "source": "kernel/process",
  "target": "channel/project-p001",
  "payload": {
    "task_id": "t_3",
    "status": "completed",
    "agent_id": "researcher",
    "token_used": 3200,
    "duration_s": 45
  },
  "metadata": {
    "project_id": "p001",
    "channel_id": "channel/project-p001",
    "thread_id": null
  },
  "visibility": "project",
  "timestamp": "2026-06-06T12:00:00Z"
}
```

支持的事件类型：
- `chat.message.posted` / `chat.message.replied`
- `agent.status.changed`
- `project.created` / `project.completed` / `project.failed`
- `project.task.updated` / `project.task.blocked`
- `project.gate.completed` / `project.gate.rejected`
- `project.deliverable.ready`
- `project.triage.requested`
- `resource.file.uploaded`
- `budget.threshold.reached`

### 5.2 Job

```json
{
  "job_id": "job_xxxx",
  "project_id": "p001",
  "status": "running",
  "pid": 12345,
  "started_at": "2026-06-06T12:00:00Z",
  "updated_at": "2026-06-06T12:05:00Z",
  "cancel_requested": false,
  "error": null
}
```

### 5.3 Agent Runtime

```json
{
  "agent_id": "researcher",
  "status": "busy",
  "last_seen": "2026-06-06T12:05:00Z",
  "current_task": "t_3",
  "current_project": "p001",
  "backend": "opencode",
  "model": "claude-sonnet-4-6",
  "workspace_ok": true
}
```

### 5.4 Manifest (`/.well-known/myteam.json`)

```json
{
  "workspace": {
    "id": "myteam-workspace",
    "version": "1.0.0"
  },
  "api": {
    "base_url": "http://localhost:8765",
    "version": "v1"
  },
  "backends": ["opencode", "claude"],
  "agents": [
    { "id": "main", "capabilities": ["team_config", "task_plan", "triage"] },
    { "id": "researcher", "capabilities": ["research"] }
  ],
  "task_types": ["team_config", "task_plan", "research", "strategy", "evaluate", "review", "triage"],
  "sse_endpoints": ["/api/workspace/events/stream", "/api/obs/projects/{id}/events"],
  "auth_mode": "optional"
}
```

---

## 6. 升级完成后的 API 全景

### 6.1 核心 API

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/status` | Hub 健康检查 |
| GET | `/.well-known/myteam.json` | Manifest |
| POST | `/api/init` | 运行 `--init`（幂等创建 workspace） |
| POST | `/api/demo` | 运行 Demo 项目 |

### 6.2 项目 API

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/projects` | 项目列表 |
| POST | `/api/projects` | 创建项目（goal, mode, budget, backend） |
| GET | `/api/projects/{id}` | 项目详情 |
| POST | `/api/projects/{id}/run` | 启动 kernel job |
| POST | `/api/projects/{id}/cancel` | 取消运行 |
| DELETE | `/api/projects/{id}` | 删除项目 |

### 6.3 可观测 API

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/obs/projects/{id}/overview` | 项目概要 |
| GET | `/api/obs/projects/{id}/tasks` | 任务列表（含 DAG 依赖） |
| GET | `/api/obs/projects/{id}/deliverables` | 交付物列表 |
| GET | `/api/obs/projects/{id}/deliverables/{path}` | 单文件内容 |
| GET | `/api/obs/projects/{id}/cost` | 成本明细 |
| GET | `/api/obs/projects/{id}/events` | 项目事件流（SSE） |
| GET | `/api/obs/agents` | Agent 运行时状态列表 |

### 6.4 Workspace API

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/workspace/events` | 事件查询（project, type, limit） |
| GET | `/api/workspace/events/stream` | 事件 SSE |
| GET | `/api/workspace/channels` | 频道列表 |
| POST | `/api/workspace/channels` | 创建频道 |

### 6.5 资源 API

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/resources` | 资源索引（project, type） |
| POST | `/api/projects/{id}/files` | 上传文件 |

### 6.6 Job API

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/jobs/{id}` | 查询 job 状态 |
| GET | `/api/jobs` | job 列表 |

### 6.7 统一错误响应

所有 API 错误统一格式：

```json
{
  "error": {
    "code": "WORKSPACE_NOT_FOUND",
    "message": "找不到 agent「researcher」的工作空间",
    "hint": "请执行 run_kernel --init 或 Hub 首页「初始化 Agent」",
    "doc_url": "/docs/troubleshooting.html#workspace-not-found"
  }
}
```

---

## 7. 视觉与设计系统（升级后）

### 7.1 主题

- **暗色主题**：保留现有的深空紫品牌色 + 毛玻璃效果（已是最强项）
- **亮色主题**：完全重构
  - 暖白基调（#f8f9fa → #ffffff），层次分明
  - 毛玻璃改为半透明白 + 细微阴影
  - 品牌色 #4f46e5（更饱和 indigo）

### 7.2 设计令牌补齐

- `--font-weight-medium/semibold/bold`（500/600/700）
- `--z-index` 层级系统
- `--line-height` 系统
- `--opacity` 层级
- 完整的 4px 间距网格（--space-0 到 --space-11）

### 7.3 CSS 模块

```
tokens.css        — 设计变量
layout.css        — 布局（导航/侧栏/主内容）
components.css    — 组件（Button/Card/Modal/Badge/…）
pages.css         — 页面级样式
```

### 7.4 JS 模块

```
ui-core.js        — 共用函数、渲染器、事件委托
chat.js           — Chat tab
projects.js       — Projects tab（含 DAG 组件）
agents.js         — Agents tab
groups.js         — Groups tab
settings.js       — Settings tab
```

### 7.5 组件库（原子设计）

**基础原子**：Button（6 变体）/ Input / Badge / Tooltip / Toast / Modal / Spinner
**复合分子**：Card（stat/project/agent）/ Table（可排序/可筛选）/ Tab（一级/二级/胶囊）/ Message Bubble / Tree View / Empty State
**组织模板**：Page Layout / Form Section / Data Dashboard

---

## 8. 升级完成后的技术架构

```
┌─────────────────────────────────────────────────┐
│                   浏览器 (Frontend)               │
│  Home │ Chat │ Groups │ Projects │ Agents │ Settings │
│  ┌─────────────────────────────────────────────┐ │
│  │  SVG DAG │ SSE Stream │ Monaco Preview...   │ │
│  └─────────────────────────────────────────────┘ │
└──────────────────┬──────────────────────────────┘
                   │ HTTP / SSE
┌──────────────────▼──────────────────────────────┐
│              Hub API (FastAPI)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ Chat     │ │ Projects │ │ Observability    │  │
│  │ Router   │ │ Router   │ │ Router           │  │
│  └────┬─────┘ └────┬─────┘ └────────┬─────────┘  │
│       │            │                │             │
│  ┌────▼────────────▼────────────────▼──────────┐  │
│  │           Services Layer                      │  │
│  │  ChatService │ ProjectService │ NotifyService │  │
│  └──────────────────┬───────────────────────────┘  │
│                     │                              │
│  ┌──────────────────▼───────────────────────────┐  │
│  │           Supervisor / Job Manager            │  │
│  └──────────────────┬───────────────────────────┘  │
└──────────────────┬──────────────────────────────┘
                   │ subprocess / file
┌──────────────────▼──────────────────────────────┐
│           Orchestration Kernel                    │
│  Process → PlanExpander → Gate                    │
│  → TaskPipeline / DecisionPipeline                │
│  → AgentPort → agent_transport                    │
│  → adapters/opencode | claude                     │
│  → CLI subprocess                                  │
└──────────────────┬──────────────────────────────┘
                   │ read/write
┌──────────────────▼──────────────────────────────┐
│              SQLite Store                         │
│  tasks/state.db  （真相：projects/tasks/events）  │
│   + workspace_events 投影（双写兼容）              │
└─────────────────────────────────────────────────┘
```

---

## 9. 升级完成状态下的核心工作流

### 9.1 项目创建与执行

```
用户填 Goal → POST /api/projects → 创建 Store 记录 → 自动创建项目频道
  → POST /api/projects/{id}/run → Supervisor 创建 job 记录
  → 启动 run_kernel subprocess → Process 加载 DAG
  → 推进 node → AgentPort → CLI 执行 → Gate 校验
  → 每次状态变更写 Store + 推 WorkspaceEvent SSE
  → 前端 DAG 图/执行树/时间线 实时更新
  → 全部 completed → Supervisor 标记 job 完成
  → 项目频道推送完成摘要
```

### 9.2 取消与恢复

```
用户点「取消」→ POST /api/projects/{id}/cancel → Store jobs.cancel_requested=true
  → Supervisor 发送 SIGTERM → Process 检查 cancel_requested → 安全终止
  → Store 标记 cancelled → 事件推送
  → Hub 前端更新状态

Hub 重启后 → Supervisor 扫描 Store jobs WHERE status=running
  → 标记为 orphan → 通知用户「上次项目异常终止，可重试」
```

### 9.3 交付物浏览

```
用户点「交付物」tab → GET /api/obs/projects/{id}/deliverables
  → Store 查询 task → 聚合 deliverables 路径
  → 前端渲染文件树 → 点击文件 GET /api/obs/projects/{id}/deliverables/{path}
  → 返回内容 + MIME → 预览 panel 渲染 Markdown/文本
```

---

## 10. 不做的事（明确边界）

以下能力在升级范围外，**不实现**：

1. **进程内 Agent**（保持 CLI 子进程隔离）
2. **JSON 抢救/修补**（拒绝无效输出，不模糊容忍）
3. **轮次（round）驱动**（保持 DAG 拓扑推进）
4. **全量 JSON 序列化**（保持 SQLite 增量持久化）
5. **DID / 去中心化身份**（无需求）
6. **跨网络 Federation**（保持本地优先）
7. **gRPC 多 Transport**（HTTP + SSE 够用）
8. **桌面 Launcher**（不增加交付渠道）
9. **公网 Tunnel**（安全风险高）
10. **完整第三方插件市场**（不引入生态管理复杂度）

---

## 11. 验收全景（Definition of Done）

### 11.1 自动化

- [ ] `pytest backend` 全绿，耗时 <60s
- [ ] CI（GitHub Actions 或等效脚本）在提交前可一键运行
- [ ] 每次 PR 自动跑测试，失败阻断合并

### 11.2 新用户 Demo

- [ ] 全新 checkout：Hub 首页 → Init → Demo → **5 分钟内** completed
- [ ] 全程可不打开终端
- [ ] Demo 完成后可在 Hub 浏览交付物

### 11.3 产品闭环

- [ ] Hub 创建自定义项目并启动（填 Goal → 选模式 → 设预算）
- [ ] 运行中可见进度条 + DAG 图 + 执行树实时更新
- [ ] 完成后 Deliverables 预览（Markdown 渲染）+ 下载
- [ ] 项目频道/时间线可见主要事件（task/gate/deliverable/triage）
- [ ] 故意制造失败时，Hub 显示中文原因 + 建议操作 + 排查链接

### 11.4 架构不变

- [ ] 无 JSON 抢救路径（submit_result 本地校验不削弱）
- [ ] Gate 同源校验（down-link spec = check-link spec）
- [ ] Adapter 隔离审查通过（UI/Hub 不引用 CLI 专有字段）
- [ ] `run_kernel` 不依赖 Hub 仍可独立跑项目

### 11.5 页面完整性

- [ ] Home：空态引导（未 init / 无项目）/ 统计卡片 / 项目网格
- [ ] Chat：三栏消息 / 轮次分割 / thinking 折叠 / @mention 补全
- [ ] Groups：发言人标识 / @mention 补全
- [ ] Projects：概览/DAG/执行/交付/成本/时间线 六个子页完整
- [ ] DAG 图：SVG 拓扑/节点着色/点击详情
- [ ] 交付物：文件树/预览/下载/标记最终
- [ ] 成本：表格+柱状图+饼图+预算告警
- [ ] 时间线：WorkspaceEvent 统一视图
- [ ] Agents：卡片+抽屉编辑/状态展示
- [ ] Settings：Accordion 分组/CLI 配置说明
- [ ] 项目频道：自动创建/事件流入/thread 支持

### 11.6 设计系统

- [ ] 亮色主题 100% 覆盖关键路径
- [ ] 设计令牌补齐（font-weight / z-index / line-height / opacity）
- [ ] CSS 拆 4 模块，单文件 <600 行
- [ ] JS 拆 6 模块，单文件 <800 行

### 11.7 文档

- [ ] quick-start.md 与 Hub 行为一致
- [ ] glossary.md 含 WorkspaceEvent / Job / Channel 新术语
- [ ] troubleshooting.md 错误码与 Hub 错误提示同步

---

## 12. 与升级前对比一览

| 维度 | 升级前 | 升级后 |
|------|--------|--------|
| **入口** | CLI 为主，Hub 为辅 | Hub 为主，CLI 为高级入口 |
| **新用户路径** | 读文档+配环境 30-60min | Hub 引导 5min 跑通 Demo |
| **项目创建** | 终端 `run_kernel` + 手写配置 | Hub 填 Goal + 选模式 + 一键启动 |
| **执行可视化** | 终端日志 | DAG 图 + 进度条 + 实时 SSE |
| **交付物** | 翻 `deliverables/` 目录 | Hub 预览 + 下载 + 标记最终 |
| **失败处理** | Python traceback | 中文原因 + 建议 + 排查链接 |
| **协作空间** | Chat/Groups/Projects 分裂 | 统一频道 + 时间线 + @mention |
| **Agent 管理** | 表格内联编辑 | 卡片 + 抽屉 + 运行时状态 |
| **成本** | 表格数字 | 柱状图 + 饼图 + 预算告警 |
| **项目管理** | 进程内存态 | 持久化 Job + 取消/恢复 |
| **工程保障** | 无 CI，全量 pytest 挂起 | CI 全绿 <60s |
| **安全** | 0.0.0.0 无鉴权 | 可选 Token + 默认 127.0.0.1 |
| **设计系统** | 暗色优/亮色弱/单体 CSS | 双主题完整/模块化 CSS+JS |
| **对外能力** | 无 | Manifest / 资源索引 / 文件上传 |

---

## 13. 参考文档

| 文档 | 对本愿景的贡献 |
|------|---------------|
| [myteam-upgrade-comprehensive-plan.md](./myteam-upgrade-comprehensive-plan.md) | **唯一入口**：上篇终态 + 下篇 R0–R4 执行 |
| [myteam-upgrade-requirements.md](./myteam-upgrade-requirements.md) | 已归档，内容已合并 |
| [product-assessment-report.md](./product-assessment-report.md) | 产品成熟度评分、Phase A/B/C 优先级、竞品对标 |
| [system-assessment-report.md](./system-assessment-report.md) | 工程短板 P0/P1、测试修复、Phase 1-4 路线图 |
| [product-improvement-plan.md](./product-improvement-plan.md) | A1-B2 详细验收条目、错误信息映射表 |
| [user-perspective-product-analysis.md](./user-perspective-product-analysis.md) | 用户旅程 P0-P2 缺口、6 条最高 ROI UI 改进 |
| [ui-design-assessment-and-upgrade-plan.md](./ui-design-assessment-and-upgrade-plan.md) | 分模块 UX 审计、设计系统、CSS/JS 模块化计划 |
| [metagpt-comparison-analysis.md](./metagpt-comparison-analysis.md) | 内核增强 B/C、禁止借鉴项 |
| [OPENAGENTS_MYTEAM_UPGRADE_CHECKLIST.md](./OPENAGENTS_MYTEAM_UPGRADE_CHECKLIST.md) | Workspace 对标、Milestone 1-5 实施顺序 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 系统 invariant、三层边界 |
| [framework-decisions.md](./framework-decisions.md) | D1-D19 设计决策 |

---

*本文档已归档。请使用 [`myteam-upgrade-comprehensive-plan.md`](./myteam-upgrade-comprehensive-plan.md) 作为唯一入口。*