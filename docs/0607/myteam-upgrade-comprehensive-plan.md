# myteam 升级完整方案

> **文档类型**：产品愿景 + 研发规格 + 验收标准（统一入口）  
> **编写日期**：2026-06-06  
> **代码基线**：分支 `upgrade/continued`  
> **状态**：终稿  
> **受众**：main / developer / frontend 等全体研发 agent  
> **上游输入**：docs/ 下 2026-06-06 各专项调研报告（见 §17）  
> **取代**：[`myteam-upgrade-requirements.md`](./myteam-upgrade-requirements.md) + [`myteam-upgrade-complete-vision.md`](./myteam-upgrade-complete-vision.md)（已标归档，勿再执行）

---

## 0. 执行速查（研发 agent 日常引用）

| 阶段 | 核心交付（3 条） | 阶段门禁（完成才可进入下一阶段） |
|------|------------------|----------------------------------|
| **R0** | SSE 测试稳定；deliverable API 修复；CI + lifespan | `pytest backend -q` 全绿 <60s |
| **R1** | Demo 目录化；Hub Init/Demo/建项+启项；交付物预览 | 无终端：Hub Demo 跑通 + 交付物可预览 |
| **R2** | WorkspaceEvent 双写；Job Supervisor；项目频道 | 事件 API/SSE 可查；job 取消/恢复可用 |
| **R3** | DAG 图；时间线 UI；Chat/Groups UX；前端模块化 | §14.5 页面清单逐项可演示 |
| **R4** | 资源索引；Manifest；鉴权；Chat 附件（可选） | 按产品需要勾选，不阻塞 R1–R3 |

**阅读顺序**：§0（本表）→ 上篇 §1–§8（终态）→ 下篇 §9–§18（执行）→ §14（总验收）。

**冲突裁决**：`CLAUDE.md` invariant > `framework-decisions.md` > 本文档。

---

# 上篇 · 升级终点：能力、体验与效果

> 上篇描述「升级完毕后 myteam 是什么样子」。研发 agent 开工前先读上篇建立目标感，再转到下篇看具体实现路径。

---

## 1. 执行摘要

### 1.1 升级定位

myteam 已完成**编排内核工业化**（Process / AgentPort / Gate / Store / Interaction 契约），当前瓶颈不在「能不能跑」，而在**产品闭环、Hub 一体化、工程可信**。

本次升级的目标形态：

**从「带 Hub 的本地多 Agent 编排器」→「可长期运行、可追踪、可协作的 Agent Team Workspace」。**

升级原则：

1. **强化内核差异化**（确定性 DAG + Gate + 契约），不削弱为「聊天壳子」
2. **补齐产品闭环**（跑通 → 看见 → 理解 → 拿交付物 → 修失败）
3. **Hub 与内核一体化**（终端与浏览器双轨收敛为「Hub 为主、CLI 为辅」）
4. **工程先行**（测试/CI 可信后再大规模改 UI）

### 1.2 升级后一句话描述

用户打开 Hub，**5 分钟内完成初始化并跑通 Demo**；在浏览器内**创建项目、填写 goal、启动编排、实时看 DAG 与进度、在项目频道追踪全链路事件、浏览/下载交付物、失败时获得可操作建议**；编排内核仍通过**Interaction 契约 + Plan Gate + Gate** 保证确定性执行。

### 1.3 分阶段交付总览

| 阶段 | 主题 | 周期 | 交付物 |
|------|------|------|--------|
| **R0** | 工程可信底座 | 1–2 周 | CI 全绿、交付物 API 修复、SSE 测试稳定 |
| **R1** | 产品闭环（CLI + Hub 基础） | 2–3 周 | Demo 目录化、Hub 建项/启项、交付物闭环、友好错误 |
| **R2** | Agent Workspace 一体化 | 3–5 周 | WorkspaceEvent、项目频道、Job Supervisor、统一时间线 |
| **R3** | 体验与可视化升级 | 3–4 周 | DAG 图、UI 模块化、Onboarding、成本/Agent 可视化 |
| **R4** | 资源层与对外能力 | 按需 | 共享资源索引、Manifest、可选鉴权 |

---

## 2. 现状基线

### 2.1 已具备的核心资产（禁止回归）

| 资产 | 证据 | 研发约束 |
|------|------|----------|
| 三层边界（Kernel / Registry / Skill） | `process.py` 282 行 + 6 子模块 | 新能力不得破坏分层 |
| Interaction 契约（6 kind） | `contracts.py` + `submit_result` | 禁止 JSON 抢救路径 |
| Plan Gate 确定性校验 | `plan_gate.py` | DAG/agent/task_type 硬校验保留 |
| Adapter 隔离 | `backend/adapters/` | UI/Hub 不得引用 CLI 专有字段 |
| SQLite 真相库 | `store.py` | 状态以 Store 为准 |
| 断点续跑 / workspace GC | `task_pipeline` + `agent_port` | 崩溃恢复语义不得弱化 |
| `--init` / `--demo` | `run_kernel.py` | 保留并增强，不删除 |
| 用户文档 6 篇+ | quick-start / user-guide 等 | 与 Hub 行为保持一致 |

### 2.2 已部分完成但仍未闭环

| 项 | 现状 | 缺口 |
|----|------|------|
| 新用户路径 | CLI `--init`/`--demo` 可用 | Hub 不能独立完成；Home 空态无引导 |
| 交付物浏览 | 前端有 Deliverables 页 | API 回归失败（2 例）；下载/预览体验弱 |
| 项目可观测 | Obs API + Projects 四 tab | 无 DAG 图；Chat/Project/Obs 数据分裂 |
| 错误友好化 | run_kernel 部分改善 | Hub/API 仍偏技术堆栈 |
| Demo | 逻辑内嵌 `run_kernel` | 缺 `business/demo/` 目录化模板 |
| 测试 | 205 例 | 全量 pytest 挂起；无 CI |

### 2.3 成熟度评分

| 维度 | 当前 | 升级目标 |
|------|:----:|:--------:|
| 编排内核架构 | 4.5 | ≥4.5（保持） |
| 测试与 CI | 3.0 | ≥4.0 |
| 产品体验 | 2.5 | ≥4.0 |
| Hub / 前端工程 | 2.5 | ≥3.5 |
| 安全与运维 | 2.0 | ≥3.0（局域网场景） |

---

## 3. 升级后能力全景

### 3.1 用户侧能力矩阵

| 能力域 | 升级前 | 升级后 |
|--------|--------|--------|
| **Onboarding** | 读文档 + CLI | Hub 检测未 init → 引导 init/demo → 首次交付物 |
| **项目创建** | 仅 CLI `run_kernel` | Hub 填 goal/模式/预算 → 一键启动 |
| **编排执行** | 终端看日志 | Hub 实时 DAG + 进度 + SSE 事件 |
| **协作沟通** | DM/群聊与项目割裂 | 项目频道 + 统一时间线 + @mention |
| **交付物** | 翻文件系统 | 预览/下载/标记最终交付/版本对比 |
| **失败处理** | 堆栈/日志 | 人话原因 + 建议动作 + 跳转排查 |
| **Agent 管理** | 表格内联编辑 | 能力卡片 + 运行时状态 + 配置校验 |
| **成本管控** | 表格数字 | 图表 + 预算告警 |
| **长期运行** | 进程内存态 | Job Supervisor 持久化 + 取消/恢复 |

### 3.2 系统侧能力矩阵

| 能力域 | 升级后规格 |
|--------|------------|
| **WorkspaceEvent** | 聊天、任务、Gate、资源、Agent 状态统一事件模型；可查询、可 SSE、可投影 |
| **频道模型** | `direct/{agent}`、`channel/general`、`channel/project-{id}` + thread |
| **Job Supervisor** | job 表持久化；启动/取消/崩溃标记；Hub 重启可查询 |
| **资源索引** | file/context/skill/tool 统一元数据；prompt 可引用地址 |
| **Manifest** | `/.well-known/myteam.json` 暴露只读能力清单 |
| **事件处理链** | persistence → notification(SSE) → projection → audit |
| **友好错误** | 错误码 + 用户文案 + troubleshooting 链接 |
| **CI 门禁** | `pytest backend` <60s 全绿 |

### 3.3 内核增强（不破坏 invariant）

| 增强项 | 来源 | 说明 |
|--------|------|------|
| Interaction 内部结构化阶段 | MetaGPT 借鉴 B | `build_worker_prompt` 对 execute/review 加入收集→产出→自检引导 |
| 运行时递归展开 | MetaGPT 借鉴 C | `needs_review` 且范围过大时原地展开子 DAG（深度上限 3） |
| 有限并行（远期） | D12 评估 | 独立任务并发，Store 锁语义清晰后再做 |

**明确不做**：进程内 Agent、JSON 抢救、轮次驱动、全量 JSON 序列化、完整插件市场、DID/federation。

---

## 4. 升级后的用户感知

### 4.1 用户类型与感受

| 用户类型 | 升级前感受 | 升级后感受 |
|----------|------------|------------|
| 技术用户 | 内核强但工具感 | 一个 Workspace 搞定聊天+编排+交付 |
| 产品/业务用户 | 门槛高、卖点看不见 | DAG/进度/交付物可见，失败能自助 |
| 团队管理者 | 难追踪多项目 | 项目列表+成本+历史+通知 |

### 4.2 完整用户旅程

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
  │       ├─ DAG 图：SVG 拓扑、节点着色、点击看任务详情
  │       ├─ 执行树：交互式层级、紧凑/展开切换、状态过滤
  │       ├─ 交付物：文件树 + Markdown/文本预览 + 下载 + 最终交付标记
  │       ├─ 成本：柱状图+饼图+预算告警
  │       └─ 时间线：统一 WorkspaceEvent 视图
  │
  ├─ 运行中
  │   └─ 项目频道自动推送：task 状态 / Gate 结果 / deliverable 就绪 / triage / 预算事件
  │
  └─ 完成后
      └─ 交付物可预览/下载/标记最终版本 → 导出摘要 → 创建下一个项目
```

### 4.3 量化成功标准

| 指标 | 基线 | R1 目标 | R2+R3 目标 |
|------|------|---------|------------|
| 新用户首次跑通 | 30–60 min | CLI <5 min | Hub <5 min（无终端） |
| 自助排查成功率 | ~0% | >60%（CLI） | >75%（Hub 含链接） |
| 跑完到看见交付物 | 需翻目录 | Hub 可浏览 | 预览+下载+标记 |
| 编排卖点可感知 | 列表为主 | 进度条+状态色 | DAG 图+时间线 |
| 测试回归 | 不可靠 | 逐模块绿 | CI 全绿 <60s |
| Hub 独立完成项目 | 否 | 创建+启动 | 创建+启动+频道协作 |

---

## 5. 升级后页面与信息架构

### 5.1 全局导航

6 个一级 Tab，一级 Tab 为全局上下文切换，二级导航用于深度内容：

```
[Home] [Chat] [Groups] [Projects] [Agents] [Settings]
```

| Tab | 升级后职责 |
|-----|------------|
| **Home** | 统计卡片（含趋势微标）+ 项目网格 + **空态引导（Init/Demo/建项）** |
| **Chat** | 单 Agent DM；与项目事件可跳转关联 |
| **Groups** | 群组 + **@mention 下拉补全** + 发言人标识 |
| **Projects** | 项目列表 → 项目工作台（见 5.2） |
| **Agents** | Agent 名册 + 能力/状态/任务类型卡片 |
| **Settings** | Accordion 分组；CLI 与 Hub 配置关系说明 |

### 5.2 Projects 项目工作台（二级导航）

```
Projects > {project_name} > [概览 | DAG | 执行 | 交付 | 成本 | 时间线]
```

#### 概览
- 项目状态徽章（running / completed / failed / cancelled）
- 整体进度条（任务完成数/总数）
- 基本信息：Goal、Mode、Budget、Backend、创建时间
- Fleet 摘要：参与 Agent 列表 + 各状态计数
- 快捷操作：取消运行 / 重试 / 删除项目

#### DAG 图（核心差异化卖点）
- SVG/Canvas 拓扑图：任务节点 + 依赖有向边
- 节点着色：completed（绿）/ running（蓝）/ failed（红）/ blocked（灰）/ pending（淡蓝）
- 点击节点 → 弹出任务详情抽屉（状态 / Agent / Token / 耗时 / 交付物 / 错误信息）
- 支持缩放平移；图例说明

#### 执行
- 交互式任务树：层级缩进 + 展开/折叠
- 紧凑模式 / 展开模式切换
- 按状态过滤：全部 / 运行中 / 已完成 / 失败 / 阻塞
- SSE 实时更新，新事件 2 秒淡黄色高亮动画
- 每行：任务 ID / Agent / task_type / 状态色标 / Token / 耗时

#### 交付物
- 左侧：文件树（按 task 分组）
- 右侧：预览面板（Markdown 渲染 / 纯文本 / 下载 / 标记最终交付）
- 版本对比（同一文件多版本时）
- 项目级聚合交付物列表

#### 成本
- 数据表格：Task / Agent / Token 输入 / Token 输出 / 总 Token / 成本
- 柱状图（按 Agent）：每个 Agent 的 Token 消耗
- 饼图：各 Agent Token 占比
- 预算告警条：已用 / 总预算，接近 80% 变黄、超预算变红

#### 时间线（统一 WorkspaceEvent）
- 时间线视图：合并 Chat / Task / Gate / Deliverable / Triage / Budget 事件
- 格式：时间戳 + 事件类型徽章 + 摘要 + 详情链接
- SSE 增量推送，新事件 2 秒高亮
- 过滤：按事件类型、按 Agent、按时间范围

### 5.3 页面详情

#### Home 仪表盘

**空态（首次使用，无项目）**：
- 居中插图 + 文案：「欢迎使用 myteam Agent Team Workspace」
- 三按钮：**初始化 Agent** / **运行 Demo** / **创建项目**
- 底部链接：快速开始文档（Hub 内嵌）

**常态（有项目历史）**：
- 顶部统计行：项目总数、运行中、本月 Token、累计成本——每个附带趋势微标（↑↓）
- 项目网格卡片：项目名 / 状态色标 / 最近活动时间 / 快捷入口
- 右侧快捷操作：「新建项目」「运行 Demo」「查看全部项目」

#### Chat — 单 Agent 对话

- 左侧：Agent 列表（头像 / 名称 / 在线状态 / 当前任务）
- 中间主区域：消息流
  - 三栏结构：角色头像+色带 | 时间戳 | 消息内容
  - 轮次分割线：轮次序号、Token 消耗、耗时
  - Thinking 块：可折叠、行号锚点
  - 引用卡片：紧凑行内式（类似 GitHub）
  - 上下文用量指示器
- 底部：输入框 + 模型选择 + 附件上传（**R4-7 可选**，非 R1–R3 阻塞项）

#### Groups — 群组协作

- 左侧：群组列表（名称 / 成员数 / 未读）
- 中间：消息流（同 Chat 结构）
  - 群聊特有：每条消息显示发言人姓名色带 + 头像
  - @mention 输入时弹出候选面板（类似 Slack/Discord）

#### Agents — Agent 管理

- 卡片视图（可切换表格视图）：
  - Agent 头像/名称
  - Backend + Model
  - 能力标签（task_type 列表）
  - Workspace 状态（正常 / 缺失 / 错误）
  - Runtime 状态（idle / busy / error）
  - 当前任务（如有）
- 点击 → 抽屉详情：完整配置 + 编辑 + 保存/取消

#### Settings — 系统设置

- Accordion 分组折叠：
  - **系统配置**：端口、默认 Backend、模型列表
  - **Agent 配置**：注册表、Workspace 路径
  - **CLI 配置**：opencode/claude 路径与登录状态检测
  - **网络**：绑定地址、鉴权 Token
  - **关于**：版本、API 文档链接、术语说明

#### 项目频道（R2 新增）

- 项目启动时自动创建 `channel/project-{project_id}`
- 在 Projects 上下文或 Groups 下均可进入
- 自动流入：task 状态 / Gate 结果 / deliverable 就绪 / triage / 预算事件
- 支持 thread：任务讨论、review 挂线程
- @mention 可指定 Agent 响应

---

## 6. 数据模型

### 6.1 WorkspaceEvent

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

### 6.2 Job

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

### 6.3 Agent Runtime

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

### 6.4 Manifest（`/.well-known/myteam.json`）

```json
{
  "workspace": { "id": "myteam-workspace", "version": "1.0.0" },
  "api": { "base_url": "http://localhost:8765", "version": "v1" },
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

## 7. 视觉与设计系统

### 7.1 主题

- **暗色主题**：保留现有深空紫品牌色 + 毛玻璃效果（已是最强项，保持）
- **亮色主题**：完全重构
  - 暖白基调（#f8f9fa → #ffffff），层次分明
  - 毛玻璃改为半透明白 + 细微阴影
  - 品牌色 #4f46e5（更饱和 indigo）

### 7.2 设计令牌补齐

| 缺失项 | 必要性 | 建议 |
|--------|--------|------|
| `--font-weight-medium/semibold/bold` (500/600/700) | 高 | 替代分散的 `font-weight: 600` |
| `--z-index` 层级系统 | 高 | 防止 modal 被 sidebar/toast 遮挡 |
| `--line-height` 系统 | 中 | 排版一致性 |
| `--opacity` 层级（disabled/hover/active） | 中 | 替代分散 opacity 值 |
| `--space-0/7/9/10/11` | 中 | 补齐 4px 网格 |
| `--text-4xl/5xl` (36/48px) | 低 | 品牌展示 |

### 7.3 CSS 模块

```
tokens.css      — 设计变量（颜色、间距、字体、z-index）
layout.css      — 布局（导航/侧栏/主内容/响应式断点）
components.css  — 组件（Button/Card/Modal/Badge/Tab/Tree…）
pages.css       — 页面级独有样式
```

单文件行数上限：**<600 行**。

### 7.4 JS 模块

```
ui-core.js      — 共用函数、渲染器、事件委托
chat.js         — Chat tab
projects.js     — Projects tab（含 DAG 组件）
agents.js       — Agents tab
groups.js       — Groups tab
settings.js     — Settings tab
```

单文件行数上限：**<800 行**。事件绑定改用委托模式，减少逐一绑定。

### 7.5 组件库（原子设计）

- **基础原子**：Button（6 变体）/ Input / Badge / Tooltip / Toast / Modal / Spinner
- **复合分子**：Card（stat/project/agent）/ Table（可排序/可筛选）/ Tab（一级/二级/胶囊）/ Message Bubble / Tree View / Empty State
- **组织模板**：Page Layout / Form Section / Data Dashboard

---

## 8. 技术架构

```
┌─────────────────────────────────────────────────┐
│                   浏览器 (Frontend)               │
│  Home │ Chat │ Groups │ Projects │ Agents │ Settings │
│  ┌─────────────────────────────────────────────┐ │
│  │  SVG DAG │ SSE Stream │ Preview...          │ │
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
                   │ subprocess / file I/O
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

### 核心工作流

**项目创建与执行**：
```
用户填 Goal → POST /api/projects → 创建 Store 记录 → 自动创建项目频道
  → POST /api/projects/{id}/run → Supervisor 创建 job 记录
  → 启动 run_kernel subprocess → Process 加载 DAG
  → 推进 node → AgentPort → CLI 执行 → Gate 校验
  → 每次状态变更写 Store + 推 WorkspaceEvent SSE
  → 前端 DAG 图/执行树/时间线 实时更新
  → 全部 completed → Supervisor 标记 job 完成 → 频道推送摘要
```

**取消与恢复**：
```
用户点「取消」→ POST /api/projects/{id}/cancel → Store jobs.cancel_requested=true
  → Supervisor 发送 SIGTERM → Process 检查 cancel_requested → 安全终止
  → Store 标记 cancelled → 事件推送 → 前端更新状态

Hub 重启后 → Supervisor 扫描 Store jobs WHERE status=running
  → 标记为 orphan → 通知用户「上次项目异常终止，可重试」
```

**交付物浏览**：
```
用户点「交付物」tab → GET /api/obs/projects/{id}/deliverables
  → Store 查询 task → 聚合 deliverables 路径
  → 前端渲染文件树 → 点击文件 GET /api/obs/projects/{id}/deliverables/{path}
  → 返回内容 + MIME → 预览 panel 渲染 Markdown/文本
```

---

# 下篇 · 实现路径与分阶段需求

> 下篇描述「怎么建」。研发 agent 按 R0→R1→R2→R3→R4 顺序执行。

---

## 9. 架构约束（Invariant — 研发不可违反）

以下 invariant 来自 `CLAUDE.md` / `framework-decisions.md`，实现中**必须保持**：

1. **Adapter 隔离**：仅 `RunRequest` / `AgentEvent` 跨 CLI；parser 是唯一知悉 raw 格式处。UI/Hub 不得引用 CLI 专有字段。
2. **Interaction 契约**：6 kind；`submit_result` 本地校验；**无 JSON 抢救**。禁止 reintroduce 模糊修补路径。
3. **Gate 同源**：down-link registry spec = check-link spec。生成时用的 spec = 校验时用的 spec。
4. **新 task_type 先进 templates.yaml**：不得仅在 Skill 层发明任务类型。
5. **Store 为真相**：Hub/Obs 只读；文件为产物/cache。状态以 Store 为准。
6. **内核不依赖 Hub**：`run_kernel` 可独立运行；Hub 为增强层。
7. **D12 串行先行**：并行 DAG 仅作 R4 可选评估项，默认不启用。

**双轨 Agent 配置说明**（须在 UI 帮助中可见）：
- **Cursor Agent**：`.cursor/rules/`、`CLAUDE.md`
- **myteam 内核 Agent**：`agents_registry.json`、`workspace-*/`

---

## 10. 分阶段需求清单

### R0 — 工程可信底座（阻塞项，必须先做）

#### R0-1 修复测试回归

| 项 | 规格 |
|----|------|
| **背景** | `pytest backend` 全量挂起；`test_observability_api.py` SSE >120s |
| **需求** | SSE 测试加 timeout/mock 终态；205 例 <60s 全绿 |
| **模块** | `backend/common/tests/test_observability_api.py`、`backend/hub/tests/` |
| **验收** | `PYTHONPATH=backend venv/bin/python3 -m pytest backend -q` 稳定通过 |

#### R0-2 修复交付物 API

| 项 | 规格 |
|----|------|
| **背景** | `test_deliverable_read`、`test_deliverable_file_read` 失败 |
| **需求** | 对齐 `get_task_deliverable_bundle` 与 API 路径；补集成测 |
| **模块** | `backend/hub/api/server.py`、`backend/common/store.py` |
| **验收** | 上述 2 例通过；Hub 可读取 demo 项目 deliverable |

#### R0-3 引入 CI

| 项 | 规格 |
|----|------|
| **需求** | GitHub Actions 或 `scripts/test.sh`；PR/本地提交必跑 |
| **验收** | CI 文档写入 `CLAUDE.md`；失败阻断合并（若用 CI） |

#### R0-4 FastAPI lifespan 迁移

| 项 | 规格 |
|----|------|
| **需求** | `@app.on_event("startup")` → lifespan；消除 DeprecationWarning |
| **模块** | `backend/hub/api/server.py` |
| **验收** | 启动无 deprecated 警告；auto-resume 行为不变 |

**R0 阶段门禁**：`PYTHONPATH=backend venv/bin/python3 -m pytest backend -q` 稳定全绿且 <60s。

---

### R1 — 产品闭环（CLI + Hub 基础）

#### R1-1 Demo 目录化

| 项 | 规格 |
|----|------|
| **需求** | 新增 `business/demo/`：`goal.txt`、`agents_config.json`、`README.md`；`--demo` 读取该目录 |
| **约束** | demo 项目仍落 `business/tasks/project/demo-*`；仅 `one_shot`；与 project_id 互斥 |
| **验收** | 全新 checkout：`--init` → `--demo` <5min exit 0；deliverable 存在 |

#### R1-2 CLI 友好错误与进度

| 项 | 规格 |
|----|------|
| **需求** | `run_kernel` / `process` 按异常类型输出中文结构化提示 |
| **需求** | 非 verbose 模式输出任务进度条与完成摘要 |

**错误信息映射表**：

| 异常类型 | 用户消息 |
|---------|---------|
| `FileNotFoundError`（agent workspace 缺失） | 找不到 agent「{agent_id}」的工作空间。请确认 workspace 目录存在。 |
| `FileNotFoundError`（config 缺失） | 缺少配置文件 `{path}`。可执行 `--init` 生成默认配置。 |
| `RuntimeError`（task_plan agent 越界） | 编排规划失败：main 分配了名册外的 agent「{agent}」。需检查 agents_registry.json。 |
| `subprocess.CalledProcessError` | CLI 后端执行失败（exit code {code}）。请确认 CLI 安装正确且已登录。 |
| 其他 | 未知错误。详情见日志。如需帮助请附上项目目录。 |

| **验收** | 5 类常见错误无 Python 堆栈；完成时有 task 列表摘要；错误写入 `run_event` 可查询 |

#### R1-3 Hub 内创建并启动项目

| 项 | 规格 |
|----|------|
| **需求** | Projects 列表页「新建项目」：goal、mode（one_shot/recurring）、budget、可选 backend |
| **需求** | 提交后调用 Supervisor 启动 kernel job（R1 可先用线程 + 持久 job 表最小实现） |
| **需求** | Home 空态三按钮：Init / Demo / 新建（**R1 即交付核心 Onboarding**） |
| **需求** | R1 创建的 `jobs` 表 schema **即为 R2-3 基础**，R2 在其上扩展 Supervisor，禁止重写表结构 |
| **API** | `POST /api/init`、`POST /api/demo`、`POST /api/projects`、`POST /api/projects/{id}/run` |
| **验收** | 不打开终端即可完成 demo 或自定义项目启动 |

#### R1-4 交付物闭环

| 项 | 规格 |
|----|------|
| **需求** | `GET /api/obs/projects/{id}/deliverables` 稳定；单文件读取/下载 |
| **需求** | Deliverables 页：Markdown 渲染、文本预览、下载按钮 |
| **需求** | 任务级 deliverable 与 project 聚合列表 |
| **验收** | demo 跑完后在 Hub 预览主报告；下载文件内容与磁盘一致 |

#### R1-5 Hub/API 友好错误

| 项 | 规格 |
|----|------|
| **需求** | API 错误响应含 `code`、`message`、`hint`、`doc_url`（链到 troubleshooting） |
| **验收** | 故意触发 workspace 缺失、配置错误时，Hub 展示可操作文案 |

**R1 阶段门禁**：Hub Init → Demo → completed；Deliverables 可预览主报告；友好错误可在 Hub 触发并展示。

---

### R2 — Agent Workspace 一体化

#### R2-1 WorkspaceEvent 模型

| 项 | 规格 |
|----|------|
| **需求** | Store 新增 `workspace_events` 表；字段见 §6.1 数据模型 |
| **事件类型** | `chat.message.posted`、`agent.status.changed`、`project.task.updated`、`project.gate.completed`、`resource.file.uploaded` 等 |
| **策略** | **双写**：现有 chat/run_event 保留，同时投影到 WorkspaceEvent |
| **API** | `GET /api/workspace/events?project_id=&type=&limit=`；SSE `GET /api/workspace/events/stream` |
| **验收** | Store 双写 + 上述 API/SSE 可查询 demo 项目事件；时间线 tab 可占位列表（**完整 UI 见 R3-2**）；不破坏 AgentEvent/Interaction 契约 |

#### R2-2 频道与线程

| 项 | 规格 |
|----|------|
| **需求** | 三类会话：`direct/{agent_id}`、`channel/general`、`channel/project-{project_id}` |
| **需求** | 支持 `thread_id` / `parent_id`；@mention 事件落库 |
| **需求** | 项目启动自动创建项目频道；task/gate/deliverable 自动发帖到频道 |
| **验收** | 项目频道可见完整执行摘要；Context Assembler 可引用频道历史 |

#### R2-3 Job Supervisor

| 项 | 规格 |
|----|------|
| **需求** | Store `jobs` 表：`job_id,project_id,status,pid,started_at,updated_at,cancel_requested,error` |
| **需求** | 在 **R1-3 已建 `jobs` 表** 上扩展：启动/取消/崩溃标记；Hub 重启后查询 orphan；替代纯内存 `_KERNEL_RUNS` |
| **需求** | Agent runtime：`online|idle|busy|error|last_seen|current_task` |
| **验收** | Hub 重启后仍知上次 job 状态；取消项目后 Store 有记录；Agents 页显示 busy |

#### R2-4 事件处理器链

| 项 | 规格 |
|----|------|
| **需求** | 内置链：`persistence` → `notification(SSE)` → `projection` → `audit` |
| **约束** | 处理器失败不污染 kernel task 状态 |
| **验收** | 新增事件类型仅注册 handler，不改多处 SSE 逻辑 |

**R2 阶段门禁**：`GET /api/workspace/events` 返回 demo 事件；job 可取消；项目频道可见 task/gate 摘要（UI 可简）。

---

### R3 — 体验与可视化升级

#### R3-1 DAG 可视化组件

| 项 | 规格 |
|----|------|
| **需求** | Projects 子页 DAG：SVG 渲染节点与依赖边；状态着色；点击打开任务详情 |
| **数据** | `GET /api/obs/projects/{id}/tasks` + dependencies |
| **验收** | demo 项目可见至少 2 节点 DAG；failed 节点红色可点 |

#### R3-2 统一时间线 UI

| 项 | 规格 |
|----|------|
| **需求** | 项目工作台「时间线」tab；合并 chat/task/gate/deliverable；SSE 增量；新事件 2s 高亮 |
| **验收** | 单次 demo 运行可在时间线看到 created→task_updated→gate→deliverable 序列 |

#### R3-3 Onboarding 体验 polish（非重复 R1-3）

| 项 | 规格 |
|----|------|
| **背景** | Init/Demo/建项按钮与基本空态已在 **R1-3** 交付；本项只做体验增强 |
| **需求** | `GET /api/status` 或专用接口暴露 init 状态；Home 引导文案/插图 polish；首次完成 Demo 后庆祝态或下一步提示 |
| **验收** | 在 R1-3 已通前提下，Home 空态视觉与引导文案达到 §5.3 终态描述；**不重复实现 R1-3 按钮逻辑** |

#### R3-4 Chat/Groups UX

| 项 | 规格 |
|----|------|
| **需求** | 消息三栏结构；轮次分割线与 token/耗时；@mention 下拉；群聊发言人色带 |
| **验收** | @ 输入时出现 agent 列表；群聊可区分发言人 |

#### R3-5 成本可视化

| 项 | 规格 |
|----|------|
| **需求** | Cost 子页柱状图（按 agent/task）+ 饼图；接近 budget 时告警样式 |
| **验收** | 有 token 数据的项目可见图表 |

#### R3-6 Agent 页与设置页

| 项 | 规格 |
|----|------|
| **需求** | Agent 抽屉编辑+确认；Settings Accordion；内嵌术语/help 链接 |
| **验收** | 误编辑可取消；Settings 无大面积空白卡片 |

#### R3-7 前端/CSS 模块化

| 项 | 规格 |
|----|------|
| **需求** | JS/CSS 按 §7.3/§7.4 拆分；事件委托减少重复绑定 |
| **验收** | JS 主文件 <800 行；CSS 单文件 <600 行 |

#### R3-8 亮色主题重构

| 项 | 规格 |
|----|------|
| **需求** | 暖白层次 + 浅色毛玻璃阴影；主色 `#4f46e5` |
| **验收** | `[data-theme=light]` 变量 100% 覆盖关键路径 |

#### R3-9 删除项目

| 项 | 规格 |
|----|------|
| **背景** | 概览页快捷操作含「删除项目」（§5.2），需 API 与 UI 对齐 |
| **需求** | 实现 `DELETE /api/projects/{id}`：删除 Store 项目记录及关联 job 引用（deliverables 文件可保留或按配置归档，默认不删磁盘产物） |
| **需求** | 概览页「删除项目」二次确认后调用上述 API |
| **验收** | 删除后项目从列表消失；误删有确认对话框；运行中项目删除前先取消或拒绝并提示 |

**R3 阶段门禁**：§14.5 页面完整性清单可在 staging 环境逐项演示（含 DAG + 时间线 + 删除项目）。

---

### R4 — 资源层与对外能力（按需）

#### R4-1 共享资源索引

| 项 | 规格 |
|----|------|
| **需求** | `resource/file|context|skill|tool` 元数据；与 deliverables/KB/skills 双写兼容 |
| **API** | `GET /api/resources?project_id=&type=` |
| **验收** | 项目资源列表含 deliverable 与上传文件 |

#### R4-2 项目文件上传

| 项 | 规格 |
|----|------|
| **需求** | Hub 上传挂 project/channel/task；注入 worker prompt 引用 |
| **验收** | 上传文件出现在频道+资源列表；agent 任务可引用 |

#### R4-3 Workspace Manifest

| 项 | 规格 |
|----|------|
| **需求** | `GET /.well-known/myteam.json`：workspace、API version、backends、agents、task_types、skills、SSE endpoints、auth mode |
| **约束** | 只读；不暴露密钥与敏感路径 |
| **验收** | 外部脚本可读 manifest 发现 API |

#### R4-4 可选鉴权

| 项 | 规格 |
|----|------|
| **需求** | 环境变量 `MYTEAM_API_TOKEN`；Header `Authorization: Bearer` |
| **需求** | 默认 bind `127.0.0.1`；`0.0.0.0` opt-in 文档警告 |
| **验收** | 开启 token 后无 token 请求 401 |

#### R4-5 Interaction 结构化 prompt（MetaGPT B）

| 项 | 规格 |
|----|------|
| **需求** | `build_worker_prompt` 对 execute/review 增加收集→产出→自检章节 |
| **验收** | 集成测或 snapshot 测 prompt 含三段结构；行为不变 |

#### R4-6 运行时 Plan 展开（MetaGPT C）

| 项 | 规格 |
|----|------|
| **需求** | `needs_review` 且范围过大时 `PlanExpander.expand_at_runtime`；深度上限 3 |
| **验收** | 单测覆盖展开后 Gate 仍校验；深度超限走 triage |

#### R4-7 Chat 附件上传（可选）

| 项 | 规格 |
|----|------|
| **背景** | 上篇 §5.3 Chat 终态含附件；**非 R1–R3 MVP 阻塞** |
| **需求** | Chat 输入区支持上传小文件；文件进入 `resource/file` 索引（依赖 R4-1）；单聊上下文可引用 |
| **约束** | 大小/类型白名单；不上传则 Chat 仍可用 |
| **验收** | 上传后 agent 下一轮可见文件引用；未做 R4-7 时 Chat 底部无附件按钮亦视为合规 |

---

## 11. API 与数据契约

### 11.1 API 全景

| 方法 | 路径 | 阶段 | 用途 |
|------|------|------|------|
| **核心** | | | |
| GET | `/api/status` | 现有 | Hub 健康检查 |
| GET | `/.well-known/myteam.json` | R4 | Manifest |
| POST | `/api/init` | R1 | 运行 `--init` |
| POST | `/api/demo` | R1 | 运行 Demo 项目 |
| **项目** | | | |
| GET | `/api/projects` | 现有 | 项目列表 |
| POST | `/api/projects` | R1 | 创建项目（goal, mode, budget） |
| GET | `/api/projects/{id}` | 现有 | 项目详情 |
| POST | `/api/projects/{id}/run` | R1 | 启动 kernel job |
| POST | `/api/projects/{id}/cancel` | R2 | 取消 job |
| DELETE | `/api/projects/{id}` | R3 | 删除项目（见 R3-9） |
| **可观测** | | | |
| GET | `/api/obs/projects/{id}/overview` | 现有 | 项目概要 |
| GET | `/api/obs/projects/{id}/tasks` | 现有 | 任务列表（含 DAG 依赖） |
| GET | `/api/obs/projects/{id}/deliverables` | R1 | 交付物列表 |
| GET | `/api/obs/projects/{id}/deliverables/{path}` | R1 | 单文件内容 |
| GET | `/api/obs/projects/{id}/cost` | 现有 | 成本明细 |
| GET | `/api/obs/projects/{id}/events` | 现有 | 项目事件流（SSE） |
| GET | `/api/obs/agents` | R2 | Agent 运行时状态 |
| **Workspace** | | | |
| GET | `/api/workspace/events` | R2 | 事件查询 |
| GET | `/api/workspace/events/stream` | R2 | 事件 SSE |
| GET | `/api/workspace/channels` | R2 | 频道列表 |
| POST | `/api/workspace/channels` | R2 | 创建频道 |
| **资源** | | | |
| GET | `/api/resources` | R4 | 资源索引 |
| POST | `/api/projects/{id}/files` | R4 | 上传文件 |
| **Job** | | | |
| GET | `/api/jobs/{id}` | R2 | 查询 job 状态 |
| GET | `/api/jobs` | R2 | job 列表 |

### 11.2 错误响应统一形状

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

所有 API 错误统一此格式。四个字段：`code`（机器可读）、`message`（人话）、`hint`（建议动作）、`doc_url`（排查链接）。

---

## 12. 研发分工建议

| 角色/agent | 主要负责 |
|------------|----------|
| **developer（后端）** | R0（测试/CI/API 修复）、R2 Supervisor/WorkspaceEvent、R4 资源/鉴权/Manifest |
| **main（协调）** | task_plan 相关、PlanExpander 运行时展开、R4 MetaGPT B/C、验收编排 |
| **frontend** | R1 Hub 建项/交付物 UI、R3 全 UI（DAG/时间线/Onboarding/CSS 模块化） |
| **文档 agent** | 与实现同步更新 quick-start / user-guide / troubleshooting / glossary |

**建议执行顺序**：

```
R0（全员阻塞）
  │
  ├─ R1-1 Demo 目录化 (developer)
  ├─ R1-2 CLI 友好错误 (developer)
  │
  └──→ R1-3 Hub 建项/启项 (frontend + developer)
       R1-4 交付物闭环 (frontend + developer)
       R1-5 Hub/API 友好错误 (developer)
        │
        ├─ R2-1 WorkspaceEvent (developer)
        ├─ R2-3 Job Supervisor (developer)
        │
        └──→ R2-2 频道与线程 (frontend + developer)
             R2-4 事件处理器链 (developer)
              │
              └──→ R3-1 DAG 图 (frontend)
                   R3-2 时间线 UI (frontend)
                   R3-3 Onboarding (frontend)
                   R3-4 Chat/Groups UX (frontend)
                   R3-5 成本可视化 (frontend)
                   R3-6 Agent/设置页 (frontend)
                   R3-7 前端模块化 (frontend)
                   R3-8 亮色主题 (frontend)
                   R3-9 删除项目 (frontend + developer)
                    │
                    └──→ R4-* 按需（含 R4-7 Chat 附件可选）
```

---

## 13. 风险与依赖

| 风险 | 缓解 |
|------|------|
| 前端单体难增量 | R3-7 先拆文件再做大 UI，而非一次性重写 |
| WorkspaceEvent 范围膨胀 | 先双写投影，不替换 kernel 表结构。事件类型逐步添加 |
| Demo 超时 >5min | goal 仅用 research+strategy 两任务；budget 限制 |
| Supervisor 与 Process 竞态 | 单项目单 job 锁；取消通过 Store 标志位 |
| 并行 DAG 引入竞态 | 保持 R4 可选，默认 D12 串行 |
| 亮色主题改造成本高 | 仅增量修改现有变量，不引入新框架 |
| WorkspaceEvent 与现有事件流冲突 | 双写阶段两个系统并行，逐步收敛 UI |
| R1/R2 job 表重复设计 | R1-3 定 schema，R2-3 只扩展字段与 Supervisor 逻辑 |

**本次升级明确不包含**（见 §16）：`store.py` / `server.py` 大文件拆分、浏览器推送通知、虚拟滚动、Lighthouse 门禁——可在后续 refactor 迭代单独立项。

**外部依赖**：opencode/claude CLI 已安装登录；`MYTEAM_ROOT` 与 `PYTHONPATH` 正确。

---

## 14. 验收全景（Definition of Done）

### 14.1 自动化

- [ ] `pytest backend` 全绿，耗时 <60s
- [ ] CI（GitHub Actions 或等效脚本）在提交前可一键运行
- [ ] 每次 PR 自动跑测试，失败阻断合并

### 14.2 新用户 Demo

- [ ] 全新 checkout：Hub 首页 → Init → Demo → **5 分钟内** completed
- [ ] 全程可不打开终端
- [ ] Demo 完成后可在 Hub 浏览交付物

### 14.3 产品闭环

- [ ] Hub 创建自定义项目并启动（填 Goal → 选模式 → 设预算）
- [ ] 运行中可见进度条 + DAG 图 + 执行树实时更新
- [ ] 完成后 Deliverables 预览（Markdown 渲染）+ 下载
- [ ] 项目频道/时间线可见主要事件（task/gate/deliverable/triage）
- [ ] 故意制造失败时，Hub 显示中文原因 + 建议操作 + 排查链接

### 14.4 架构不变

- [ ] 无 JSON 抢救路径（submit_result 本地校验不削弱）
- [ ] Gate 同源校验（down-link spec = check-link spec）
- [ ] Adapter 隔离审查通过（UI/Hub 不引用 CLI 专有字段）
- [ ] `run_kernel` 不依赖 Hub 仍可独立跑项目

### 14.5 页面完整性

- [ ] Home：空态引导（未 init / 无项目）/ 统计卡片 / 项目网格
- [ ] Chat：三栏消息 / 轮次分割 / thinking 折叠 / @mention 补全
- [ ] Groups：发言人标识 / @mention 补全
- [ ] Projects：概览/DAG/执行/交付/成本/时间线 六个子页完整
- [ ] 概览快捷操作：取消/重试/删除项目（R3-9，删除二次确认）
- [ ] DAG 图：SVG 拓扑/节点着色/点击详情
- [ ] 交付物：文件树/预览/下载/标记最终
- [ ] 成本：表格+柱状图+饼图+预算告警
- [ ] 时间线：WorkspaceEvent 统一视图
- [ ] Agents：卡片+抽屉编辑/状态展示
- [ ] Settings：Accordion 分组/CLI 配置说明
- [ ] 项目频道：自动创建/事件流入/thread 支持

### 14.6 设计系统

- [ ] 亮色主题 100% 覆盖关键路径
- [ ] 设计令牌补齐（font-weight / z-index / line-height / opacity）
- [ ] CSS 拆 4 模块，单文件 <600 行
- [ ] JS 拆 6 模块，单文件 <800 行

### 14.7 文档

- [ ] quick-start.md 与 Hub 行为一致
- [ ] glossary.md 含 WorkspaceEvent / Job / Channel 新术语
- [ ] troubleshooting.md 错误码与 Hub 错误提示同步

---

## 15. 升级前后对比一览

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

## 16. 明确不做的工作

以下能力在升级范围外，**不实现**：

| 事项 | 理由 |
|------|------|
| 进程内 Agent（Role Python 对象） | 破坏隔离性，Agent 崩溃=框架崩溃 |
| JSON 抢修/模糊修复 | 拒绝无效输出，不模糊容忍。违反 D1/F1 |
| 轮次（round）驱动 | 不适合生产任务，无完成语义。DAG 更可预测 |
| 全量 JSON 序列化持久化 | 无事务保障，大项目不可恢复 |
| DID / 去中心化身份 | 无需求 |
| 跨网络 Federation | 保持本地优先 |
| gRPC 多 Transport | HTTP + SSE 够用 |
| 桌面 Launcher | 不增加交付渠道 |
| 公网 Tunnel | 安全风险高 |
| 完整第三方插件市场 | 不引入生态管理复杂度 |
| **`store.py` / `server.py` 模块化拆分** | 有价值但属 refactor；不阻塞产品闭环，单独迭代 |
| **浏览器推送 / Hub 角标通知** | 用户调研 P1；无 SSE 桌面通知 MVP 亦可交付 |
| **Chat 长对话虚拟滚动** | ui-design Phase 3；性能问题出现后再做 |
| **Lighthouse / WCAG 自动化门禁** | 设计指标参考 ui-design §7；非本次 DoD |
| **Chat 附件上传** | 终态见 §5.3；实现归 **R4-7 可选**，未做不视为升级未完成 |

---

## 17. 参考文档索引

| 文档 | 贡献内容 |
|------|----------|
| [product-assessment-report.md](./product-assessment-report.md) | 产品成熟度评分、Phase A/B/C 优先级、竞品对标 |
| [system-assessment-report.md](./system-assessment-report.md) | 工程短板 P0/P1、测试修复、Phase 1-4 路线图 |
| [product-improvement-plan.md](./product-improvement-plan.md) | A1-B2 详细验收条目、错误信息映射表 |
| [user-perspective-product-analysis.md](./user-perspective-product-analysis.md) | 用户旅程 P0-P2 缺口、6 条最高 ROI UI 改进 |
| [ui-design-assessment-and-upgrade-plan.md](./ui-design-assessment-and-upgrade-plan.md) | 分模块 UX 审计、设计系统、CSS/JS 模块化计划 |
| [metagpt-comparison-analysis.md](./metagpt-comparison-analysis.md) | 内核增强 B/C、禁止借鉴项 |
| [OPENAGENTS_MYTEAM_UPGRADE_CHECKLIST.md](./OPENAGENTS_MYTEAM_UPGRADE_CHECKLIST.md) | Workspace 对标、Milestone 1-5 实施顺序 |
| [refactor-baseline.md](./refactor-baseline.md) | 内核 refactor 验收 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 系统 invariant、三层边界 |
| [framework-decisions.md](./framework-decisions.md) | D1–D19 设计决策 |
| [myteam-upgrade-requirements.md](./myteam-upgrade-requirements.md) | 已归档（内容已合并至本文档下篇） |
| [myteam-upgrade-complete-vision.md](./myteam-upgrade-complete-vision.md) | 已归档（内容已合并至本文档上篇） |

---

## 18. 研发 agent 执行说明

1. **日常排期先看 §0 速查表**，再读上篇/下篇对应章节。
2. **以上篇为终点认知，以下篇为执行依据**：上篇回答「长什么样」，下篇回答「怎么建」。
3. **先读上篇（§1–§8）建立目标感**，再转到下篇（§9–§16）对照自身负责的阶段。
4. **按 R0→R1→R2→R3 顺序**执行；每阶段通过 **§0 / 各 R* 阶段门禁** 再进入下一阶段。未完成 R0 不得合并大规模 Hub 功能。
5. **每项需求提交时附带**：变更说明 + 对应验收项勾选 + 测试结果。
6. **文档同步**：用户可见行为变化时更新 `quick-start.md` / `user-guide.md` / `troubleshooting.md`。
7. **不做清单外扩展**：「不做的工作」见 §16。
8. **冲突裁决**：若本文档与 `CLAUDE.md` invariant 冲突，以 `CLAUDE.md` 为准。若本文档与 `framework-decisions.md` 冲突，以 `framework-decisions.md` 为准。

---

*本文档综合 2026-06-06 各专项 agent 调研报告编制，合并了升级需求规格与完成全景描述，作为 myteam 升级唯一入口文档。*