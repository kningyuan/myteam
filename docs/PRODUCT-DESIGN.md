# myteam 产品设计方案

> 版本：v1.0
> 日期：2026-06-26
> 状态：设计稿

---

## 一、产品定位与愿景

### 1.1 产品定位

**myteam 是一个工业级多 Agent 协作框架**，为团队提供从"单 Agent 交互式执行"到"多 Agent 结构化编排"的全链路协作能力。

它不是一个 AI 助手，而是一个**协作操作系统**——让多个 AI Agent 像一个团队一样，有分工、有流程、有质量门禁、有迭代改进，最终可靠地交付复杂任务。

### 1.2 核心价值主张

| 价值 | 说明 |
|------|------|
| **可靠性** | Gate 形式化门禁 + 多轮重试 + 同行评审，产出可预期 |
| **可扩展性** | 声明式 Workflow + 可配置角色 + 可插拔 Skill，业务扩展不改内核 |
| **可观测性** | 全链路事件追踪 + 质量画像 + 成本计量，过程透明可审计 |
| **自进化** | 经验沉淀 + Skill 提取 + 质量基线更新，越用越好 |

### 1.3 目标用户

- **技术团队**：研发团队用多 Agent 协作完成代码开发、测试、部署
- **产品团队**：产品调研、竞品分析、PRD 撰写
- **运营团队**：内容生产、社媒运营、数据报告
- **研究团队**：深度调研、文献综述、技术预研

---

## 二、产品能力全景

### 2.1 三大核心能力域

```
┌─────────────────────────────────────────────────────────────────┐
│                     myteam 协作框架                              │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  交互式执行      │  编排式交付      │  知识与经验沉淀               │
│  (Interactive)  │  (Orchestrated) │  (Knowledge & Experience)   │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ • Agent 私聊     │ • Workflow 定义  │ • 知识库 (L3)               │
│ • 群组协作       │ • 任务 DAG 编排   │ • 偏好库                    │
│ • 圆桌讨论       │ • 子任务动态拆分  │ • 工作记忆 (L1)             │
│ • Skill 工具箱   │ • Gate 形式化门禁 │ • 经验账本 (Ledger)        │
│ • MCP 工具集     │ • 同行评审       │ • Skill 自进化              │
│                 │ • Loop 循环迭代   │ • 质量画像                  │
│                 │ • 预算与成本控制  │ • 项目库                    │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

> **当前实现达标率：约 65-70%（按"功能+边界都清晰"的严格标准）**。核心功能完整（功能层面 ~80%），但系统边界清晰度仅 60%，自进化/质量画像等能力为部分实现，且多处存在硬编码架构债。
> 逐项差距评估见 [UPGRADE-GAP-ASSESSMENT.md §1.2](./UPGRADE-GAP-ASSESSMENT.md)。

### 2.2 产品能力 vs 用户配置能力

这是产品最核心的边界划分——**哪些是框架自带的，哪些是用户通过配置获得的**。

#### ✅ 产品提供的能力（系统内置，开箱即用）

| 能力域 | 具体能力 | 说明 |
|--------|---------|------|
| **执行引擎** | DAG 调度状态机 | 任务依赖调度、波次并行、断点续跑 |
| | 交互生命周期管理 | 看门狗、幂等、重试、token 计量 |
| | 形式化门禁 (Gate) | 契约校验、格式校验、完整性校验、证据校验 |
| | 失败分诊 (Triage) | retry / reassign / split / drop / abort |
| | Loop 循环机制 | until 条件循环、多 body 分支、PATCH 模式迭代 |
| | 预算控制 | token 预算、自动降级、超预算暂停 |
| **交互协议** | Interaction 统一契约 | Request/Response 辨识联合，Pydantic 强校验 |
| | AgentEvent 统一事件模型 | 跨 CLI 后端的统一事件格式 |
| | submit_result 本地校验 | Agent 侧原子交卷，拒绝而非抢救 |
| **适配器层** | 多 CLI 后端适配 | opencode / claude / Codex 可插拔 |
| | MCP 工具集成 | 标准 MCP 协议支持 |
| | Skill 同步机制 | 统一的 Skill 挂载/卸载 |
| **质量保证** | 五层质量防御体系 | PRE → Agent 自约束 → Gate → Peer Review → POST |
| | Quality 自评模型 | Agent 自评分 + known_gaps |
| | Rubric 自动化评估 | 6 维度量化评分 + 红线机制 |
| | 同行评审流程 | review task_type + acceptance_criteria |
| **协作模式** | 私聊 (DM) 模式 | 单 Agent 交互式执行 |
| | 群组 notify 模式 | 多 Agent 并发响应 |
| | 圆桌讨论模式 | 多轮立论 → 对齐 → 共识投票 |
| | 项目协作群 | 自动建群 + 进度通报 |
| **可观测性** | 全链路事件流 | run_event 时间线 + SSE 推送 |
| | 项目仪表盘 | 状态/进度/成本/任务 DAG 可视化 |
| | 审计日志 | 操作记录 + 质量追踪 |
| **自进化** | 经验沉淀 (Ledger) | 任务成功后自动写入知识库 |
| | 教训提取 (Lesson) | 失败重试后自动写入教训库 |
| | Skill 后台评审 | 任务完成后异步提取 Skill 补丁 |
| | 质量画像 | Agent 跨任务能力追踪 |

#### ⚙️ 用户配置的能力（通过配置/扩展获得）

| 能力域 | 用户配置什么 | 配置载体 |
|--------|-------------|---------|
| **角色定义** | 有哪些 Agent 角色、各角色擅长什么 | `agents_registry.json` + workspace 身份文件 |
| **任务类型** | 有哪些类型的任务、交付物格式、验收标准 | `templates.yaml`（task_type 定义） |
| **工作流** | 任务怎么编排、谁来做、依赖关系 | `business/workflows/*.yaml` |
| **技能包** | 各领域的方法论、工具使用指南 | `business/skills/*/SKILL.md` + `catalog.yaml` |
| **规则系统** | 不同场景下 Agent 的行为准则 | `business/rules/*.md` |
| **交付模板** | 各类交付物的完整模板和章节结构 | `business/delivery_templates/*.yaml` |
| **Prompt 配置** | 各类型任务的 prompt 模板和注入块 | `prompt_templates.yaml` + `prompt_injections.yaml` |
| **交付套餐** | 过程产物组合（align/plan/verify 等） | `delivery_profiles.yaml` |
| **MCP 工具** | 可用的外部工具服务 | `mcp_registry.json` |
| **任务分配规则** | 某类任务优先分配给谁 | `task_type_agent_priority.json` |
| **用户偏好** | 风格偏好、禁忌、工具偏好 | `preferences/` + `USER.md` |
| **知识库内容** | 团队知识、最佳实践、历史经验 | KB 条目（SQLite/外部 KB） |

#### 🎯 两者的边界原则

1. **机制进产品，策略归配置**：怎么做调度是产品能力，调度谁做什么任务是配置
2. **格式进产品，内容归配置**：交付物的章节骨架检查是产品能力，具体章节写什么是配置
3. **流程进产品，内容归配置**：评审的流程（谁评审、怎么评审）是产品能力，评审的具体标准是配置
4. **接口进产品，实现归配置**：Skill 的挂载/调用机制是产品能力，Skill 的具体内容是配置

#### 🖥️ **第五原则：配置必须有 UI

> **所有用户可配置的内容，必须有对应的前端管理页面。** 用户不需要手动编辑配置文件。**

这是产品的硬性要求——用户通过 UI 就能完成所有配置工作，不要求用户懂 YAML/JSON 语法、不要求用户登录服务器、不要求用户懂文件结构。

| 配置类别 | 前端页面位置 | 说明 |
|---------|------------|------|
| Agent 管理 | `/manage/agents` | Agent 列表、增删改查、身份文件编辑、Skill/MCP 挂载 |
| 任务类型管理 | `/manage/task-types` | task_type 定义、交付格式、验收标准 |
| 交付模板管理 | `/manage/templates` | 交付模板 CRUD、YAML 编辑、任务类型绑定 |
| 偏好库管理 | `/manage/preferences` | 团队偏好编辑、同步到 Agent |
| 知识库管理 | `/manage/knowledge` | KB 条目 CRUD、分类筛选、模板管理 |
| 工作流管理 | `/workflows` | Workflow 编辑器、循环配置、依赖管理 |
| Skill 管理 | `/skills` | Skill 库浏览、分类管理、待审批、覆盖度审计 |
| MCP 管理 | `/mcp` | MCP 服务 CRUD、启用/停用、参数配置 |
| 群组管理 | `/groups` | 群组 CRUD、成员管理、圆桌设置 |
| Prompt 配置 | `/manage/prompts` | Prompt 模板管理、Prompt 注入块管理 |
| 交付套餐管理 | `/manage/profiles` | delivery_profiles 配置、过程产物套餐管理 |
| 规则管理 | `/manage/rules` | 团队规则编辑、规则 profile 管理 |
| 系统设置 | `/settings/*` | 系统配置、执行配置、协作配置、质量配置 |
| 角色注册表 | `/manage/roles` | agents_registry 编辑、角色能力定义 |
| 任务分配规则 | `/manage/priorities` | task_type_agent_priority 配置 |

---

## 三、交互式执行（Agent 私聊）

### 3.1 能力描述

用户可以与单个 Agent 进行自然语言对话，Agent 可以在对话中直接执行任务——读写文件、运行命令、联网调研、使用 Skill 和 MCP 工具。

这是最灵活的使用方式，适合：
- 快速原型验证
- 探索性工作
- 简单一次性任务
- 需要人工实时干预的场景

### 3.2 产品提供的能力

| 能力 | 说明 | 验证方式 |
|------|------|---------|
| **多轮对话记忆** | 滚动摘要 + 历史召回，支持长对话 | 连续 10 轮对话后，Agent 能正确引用早期内容 |
| **全工具权限** | Read/Write/Edit/Bash/WebSearch 等全套工具 | Agent 能在对话中完成文件修改、命令执行、网页调研 |
| **身份上下文** | IDENTITY + SOUL + AGENTS 三层身份注入 | Agent 行为符合角色设定 |
| **Skill 工具箱** | 已挂载 Skill 可按需调用 | Agent 能正确使用已挂载的 Skill 完成任务 |
| **MCP 工具集** | 已配置 MCP Server 可调用 | Agent 能通过 MCP 协议调用外部工具 |
| **多 Agent 协作感知** | Agent 知道团队中有谁、各自擅长什么 | Agent 能在对话中建议转交其他角色处理 |
| **对话归档与搜索** | 历史对话可归档、可搜索 | 能在归档中搜索到历史对话内容 |
| **后台任务不中断** | 刷新页面不中断对话 | 开始长任务后刷新页面，任务继续执行 |

### 3.3 用户配置的能力

| 配置项 | 说明 | 载体 |
|--------|------|------|
| Agent 角色身份 | 角色名称、定位、能力边界、性格 | workspace/IDENTITY.md、SOUL.md、AGENTS.md |
| 挂载的 Skill 列表 | 该 Agent 可用哪些 Skill | `agents_registry.json` 的 `skills` 字段 |
| 挂载的 MCP 列表 | 该 Agent 可用哪些 MCP 工具 | `agents_registry.json` 的 `mcp_servers` 字段 |
| 后端与模型选择 | 使用哪个 CLI 后端、哪个模型 | `agents_config.json` |
| 交互行为规则 | 私聊场景下的行为准则 | `business/rules/interactive-guide.md` |
| 用户偏好 | 输出风格、格式偏好、禁忌 | `preferences/USER.md` |

### 3.4 交互流程

```
用户发消息
    ↓
消息落库 (SQLite message 表)
    ↓
组装上下文：
  ├─ 系统身份 (IDENTITY/SOUL/USER)
  ├─ 角色能力 (registry)
  ├─ 已挂载 Skill
  ├─ MCP 工具
  ├─ 多 Agent 协作上下文
  └─ 对话历史 (召回 + 滚动摘要)
    ↓
调用 CLI 适配器 (RunRequest)
    ↓
流式输出 AgentEvent → SSE 推送到 UI
    ↓
回复完成 → 写入消息表 → 更新摘要
```

---

## 四、编排式交付（Workflow 项目）

### 4.1 能力描述

用户可以定义或选择一个 Workflow，启动一个项目。框架自动按照 Workflow 定义的 DAG（有向无环图）调度多个 Agent 协作完成任务，每个任务都有形式化 Gate 门禁和可选的同行评审，任务可以动态拆分子任务，可以用 Loop 机制迭代改进，最终交付经过质量保证的产出物。

这是最可靠的使用方式，适合：
- 标准化、重复性高的任务
- 需要多角色协作的复杂任务
- 对交付质量有明确要求的任务
- 需要可审计、可追溯的任务

### 4.2 产品提供的能力

#### 4.2.1 Workflow 编排引擎

| 能力 | 说明 | 验证方式 |
|------|------|---------|
| **DAG 调度** | 按依赖关系拓扑排序，波次调度 | 定义 5 个有依赖的任务，验证执行顺序正确 |
| **并行执行** | 同波次无依赖任务可并行 | 2 个独立任务同时开始执行 |
| **断点续跑** | 中断后从断点恢复，不重跑已完成任务 | 运行中杀死进程，重启后从断点继续 |
| **任务状态机** | pending → in_progress → completed/failed/needs_review | 各状态转换符合预期 |
| **项目状态机** | pending → in_progress → completed/partially_failed/failed/aborted | 各状态转换符合预期 |

#### 4.2.2 任务拆分与子任务

| 能力 | 说明 | 验证方式 |
|------|------|---------|
| **Evaluate 评估拆分** | 任务到达时先评估是否需要拆分 | 一个复杂任务被拆分为 3 个子任务 |
| **子任务插入 DAG** | 父任务被替换为子任务组，依赖自动修正 | 下游任务正确依赖所有子任务 |
| **层级命名** | `{parent}.{sub}` 命名体现层级 | 子任务 id 清晰反映父子关系 |
| **深度保护** | max_split_depth 防止无限拆分 | 超过深度限制后不再拆分 |
| **扇出保护** | max_subtasks 限制单次拆分数 | 单次拆分不超过上限 |

#### 4.2.3 Gate 形式化门禁

| 能力 | 说明 | 验证方式 |
|------|------|---------|
| **契约门禁** | 响应必须符合 Interaction 契约 | 非法格式的响应被拒绝 |
| **格式门禁** | 必需章节、标题层级、文件存在性检查 | 缺少必需章节的交付物被 Gate 拦下 |
| **防 Stub** | 检测占位符和过短内容 | "待补充"类内容被识别为不合格 |
| **证据门禁** | action 类任务验证 URL/截图等硬证据 | 发布类任务必须有已发布 URL 和截图 |
| **代码项目门禁** 🟠 | code_project 类验证目录结构和文件（当前类型列表硬编码，P0 级配置化） | 代码交付物必须有指定文件和扩展名 |
| **自动重试** | Gate 失败自动重试，附带失败反馈 | 第 1 次失败后第 2 次修复通过 |
| **纯格式优化** | 格式类失败提供 patch_hint，减少重写 | 仅标题层级错误时，Agent 只修格式不改内容 |

#### 4.2.4 同行评审 (Peer Review)

| 能力 | 说明 | 验证方式 |
|------|------|---------|
| **评审交互** | reviewer Agent 按 acceptance_criteria 评审 | 评审产出包含 passed/feedback/checklist |
| **评审影响状态** | 通过 → completed，不通过 → needs_review | 评审未通过的任务状态正确 |
| **评审阻塞策略** | needs_review 可配置是否阻塞下游 | 阻塞模式下，下游任务被 blocked |
| **评审依据统一** | 自评和评审共用 acceptance_criteria | 两个角色使用同一套验收标准 |

#### 4.2.5 Loop 循环迭代

| 能力 | 说明 | 验证方式 |
|------|------|---------|
| **until 条件循环** | 满足退出条件前持续迭代 | review_passed 条件满足后退出循环 |
| **多 body 分支** | v2 格式支持多个 body 分支 + transition 跳转 | 根据 assess 结果切换到不同 body |
| **PATCH 模式** | 第 2+ 轮基于上一轮成果定点修改，不全文重写 | 第二轮交付物保留第一轮的正确部分 |
| **基线复制** | 上一轮交付物自动复制为本轮初稿 | 第二轮开始时有完整的基线文件 |
| **群讨论对齐** (可选) | 循环间插入群讨论，对齐改稿需求 | work agent 和 review agent 在群内讨论后再迭代 |
| **最小/最大轮数** | min_rounds 保证充分迭代，max_rounds 防止死循环 | 边界条件行为正确 |
| **断点恢复** | 从 run_event 恢复循环状态 | 中断后恢复能记住当前轮次和 body |

#### 4.2.6 失败分诊 (Triage)

| 能力 | 说明 | 验证方式 |
|------|------|---------|
| **5 种分诊决策** | retry / reassign / split / drop / abort | 各决策的效果正确 |
| **协调者决策** 🔴 | 当前硬编码为 "main" Agent，用户不可配置（P0 级架构债） | main 能根据上下文选择合理的分诊策略 |
| **决策可追溯** | 分诊决策和理由记录在案 | 能在事件流中看到 triage 决策 |

#### 4.2.7 预算与成本控制

| 能力 | 说明 | 验证方式 |
|------|------|---------|
| **Token 计量** | 全链路 token 使用量统计 | 项目结束后有准确的 token 消耗统计 |
| **预算控制** | 超预算自动暂停项目 | 达到预算上限后项目状态变为 paused |
| **自动降级** | 接近预算时自动切换轻量模型 | 预算不足时降级到 cheaper 模型 |
| **按任务/Agent 拆分** | 可查看各任务、各 Agent 的成本 | 成本报表维度正确 |

### 4.3 用户配置的能力

| 配置项 | 说明 | 载体 |
|--------|------|------|
| **Workflow 定义** | 任务 DAG、依赖关系、角色分配 | `business/workflows/*.yaml` |
| **任务类型定义** | 各 task_type 的交付物格式、验收标准 | `business/templates/templates.yaml` |
| **交付模板** | 各类型交付物的完整章节模板 | `business/delivery_templates/*.yaml` |
| **交付套餐** | 过程产物组合（align/plan/verify） | `delivery_profiles.yaml` |
| **Agent 角色** | 有哪些角色、各角色能力边界 | `agents_registry.json` + workspace 文件 |
| **Skill 包** | 各领域方法论和工具指南 | `business/skills/` |
| **规则系统** | Worker 执行规则、协作规则 | `business/rules/worker-template.md` 等 |
| **Prompt 模板** | 各任务类型的 prompt 骨架 | `prompt_templates.yaml` + `prompt_injections.yaml` |
| **运行选项** | 是否启用 review、split、parallel 等 | workflow.options 或 CLI 参数 |
| **循环配置** | max_rounds、min_rounds、退出条件等 | workflow.loops 定义 |
| **协作配置** | 是否自动建群、是否启用群讨论 | workflow.options.collaboration |

### 4.4 编排执行流程

```
用户启动项目（指定 workflow 或 goal）
    ↓
┌─ 准备阶段 ──────────────────────────────┐
│ 1. team_config（确定团队成员）           │
│    或直接从 workflow roster 加载        │
│ 2. task_plan（规划任务 DAG）            │
│    或直接从 workflow tasks 加载         │
│ 3. 可选：evaluate 静态拆分              │
│ 4. check_plan（DAG 合法性校验）          │
└─────────────────────────────────────────┘
    ↓
┌─ 执行阶段（DAG 调度循环）────────────────┐
│                                         │
│  while 有未完成任务：                    │
│    ├─ 找出所有就绪任务（ready_tasks）     │
│    ├─ 可选：动态拆分（expand_ready）     │
│    ├─ 对每个任务：                       │
│    │   ├─ 普通任务 → run_task           │
│    │   │    ├─ PRE 注入（harness）      │
│    │   │    ├─ execute（Agent 执行）    │
│    │   │    ├─ Gate 门禁                │
│    │   │    ├─ 失败 → 重试（最多 N 次） │
│    │   │    ├─ 重试耗尽 → triage        │
│    │   │    ├─ 通过 → 质量判定          │
│    │   │    ├─ 可选：peer_review        │
│    │   │    └─ POST 沉淀（异步）         │
│    │   └─ Loop 占位 → run_loop          │
│    │        └─ 循环内 DAG 调度（同上）   │
│    └─ 更新 outcomes，进入下一波          │
│                                         │
└─────────────────────────────────────────┘
    ↓
项目完成 → 产出交付物 + 质量报告 + 经验沉淀
```

### 4.5 关键状态机图

#### 4.5.1 项目状态机

```
                    ┌──────────┐
                    │ pending  │  初始状态
                    └────┬─────┘
                         │ 启动
                         ▼
                    ┌──────────┐
              ┌────▶│in_progress│  执行中
              │     └────┬─────┘
              │          │
              │    ┌─────┴─────┐
              │    │           │
              │    ▼           ▼
              │ ┌──────┐  ┌────────┐
              │ │paused│  │partially│  部分失败
              │ └──┬───┘  │_failed │
              │    │      └───┬────┘
              │    │ 恢复     │
              └────┘          │
                               │  最终判定
                               ▼
                    ┌──────────────────┐
                    │ completed /      │  终态
                    │ failed / aborted │
                    └──────────────────┘
```

**状态转换规则：**
- `pending → in_progress`：项目启动，开始 team_config
- `in_progress → paused`：预算耗尽 / 人工暂停
- `paused → in_progress`：追加预算 / 人工恢复
- `in_progress → partially_failed`：有任务最终失败但非关键路径
- `partially_failed → completed`：关键路径完成，非关键失败接受
- `partially_failed → failed`：失败任务影响交付
- `in_progress → failed`：关键任务失败且 triage 失败
- `in_progress → completed`：所有任务完成
- `in_progress → aborted`：人工中止

#### 4.5.2 任务状态机

```
                      ┌─────────┐
                      │ pending │  等待依赖
                      └────┬────┘
                           │ 依赖就绪
                           ▼
                      ┌──────────┐
                 ┌───▶│in_progress│  执行中
                 │    └────┬─────┘
                 │         │
            重试 │    ┌────┴────┐
                 │    │         │
                 │    ▼         ▼
                 │ ┌─────┐  ┌──────────┐
                 │ │ Gate│  │needs_    │  待评审（自评低触发①）
                 │ │_pass│  │review    │
                 │ └──┬──┘  └────┬─────┘
                 │    │          │
                 │    │    ┌─────┴──────┐
                 │    │    │            │
                 │    │    ▼            ▼
                 │    │ ┌───────┐  ┌──────────┐
                 │    │ │review_│  │review_   │
                 │    │ │passed │  │not_passed│
                 │    │ └───┬───┘  └────┬─────┘
                 │    │     │           │
                 └────┘     │     需修改 │
                      失败  │           │
                 ┌──────────┘           │
                 │                      │
                 ▼                      │
            ┌─────────┐                 │
            │ failed  │─── triage ──────┘
            └─────────┘    retry
                 │
            triage │
            abort/  │
            drop    ▼
                 ┌──────────┐
                 │completed │  终态
                 └──────────┘
```

> **① `Gate_pass → needs_review` 路径说明：** 并非所有 Gate 通过的任务都走评审。仅在 **Agent 自评分数低于阈值**（`Quality.score < threshold`）时触发，由框架侧根据自评结果判断。Gate 直接失败（契约/格式/证据不合格）的任务走 `重试 / triage` 路径。

#### 4.5.3 项目状态迁移矩阵

> 「状态 × 事件 → 下一状态」精确表格，是实现 Process 状态机的直接依据。

| 当前状态 ↓ \ 事件 → | start | pause | resume | complete | fail | partial_fail | abort |
|---------------------|-------|-------|--------|----------|------|--------------|-------|
| **pending** | in_progress | - | - | - | - | - | - |
| **in_progress** | - | paused | - | completed | failed | partially_failed | aborted |
| **paused** | - | - | in_progress | - | - | - | aborted |
| **partially_failed** | - | - | - | completed | failed | - | aborted |
| **completed** | - | - | - | - | - | - | - |
| **failed** | - | - | - | - | - | - | - |
| **aborted** | - | - | - | - | - | - | - |

**说明：**
- `-` 表示非法转换，不应发生；发生则视为 bug
- `partially_failed → completed`：需要人工确认接受部分失败
- `partially_failed → failed`：失败任务影响核心交付物
- `paused → aborted`：人工中止暂停中的项目

#### 4.5.4 任务状态迁移矩阵

> 任务级状态迁移矩阵，是 Gate 和 Process 调度的核心依据。

| 当前状态 ↓ \ 事件 → | ready | start | gate_pass | gate_fail | review_start | review_pass | review_fail | retry_exhaust | triage_retry | triage_reassign | triage_split | triage_drop | triage_abort |
|---------------------|-------|-------|-----------|-----------|--------------|-------------|-------------|----------------|--------------|-----------------|--------------|-------------|--------------|
| **pending** | - | in_progress | - | - | - | - | - | - | - | - | - | - | - |
| **in_progress** | - | - | ✅ see below | - | needs_review | - | - | - | - | - | - | - | - |
| **gate_pass** | - | - | - | - | needs_review | completed | - | - | - | - | - | - | - |
| **needs_review** | - | - | - | - | - | completed | in_progress | - | - | - | - | - | - |
| **gate_fail** | - | - | - | - | - | - | - | failed | in_progress | in_progress | pending | completed | aborted |
| **failed** | - | - | - | - | - | - | - | - | in_progress | in_progress | pending | completed | aborted |
| **completed** | - | - | - | - | - | - | - | - | - | - | - | - | - |
| **aborted** | - | - | - | - | - | - | - | - | - | - | - | - | - |

**说明：**
- **in_progress → gate_pass → needs_review/completed**：取决于是否启用 review；启用走 review 路径，不启用直接 completed
- **gate_fail → failed**：重试次数耗尽且 triage 未选择重试/重分配
- **failed → in_progress (triage_retry)**：triage 决定重试，从原状态重跑
- **failed → in_progress (triage_reassign)**：triage 决定换个 Agent 重跑
- **failed → pending (triage_split)**：triage 决定拆分，父任务被替换为子任务组
- **failed → completed (triage_drop)**：triage 决定放弃该任务（非关键路径）
- 所有 triage 决策都需要协调者 Agent 判断，不是自动的

### 4.6 DAG 调度流程图

```
         ┌─────────────────────────────┐
         │   获取当前项目所有任务        │
         └──────────────┬──────────────┘
                        │
                        ▼
         ┌─────────────────────────────┐
         │  找出所有就绪任务：           │
         │  status == pending          │
         │  && 所有依赖任务 completed   │
         └──────────────┬──────────────┘
                        │
              ┌─────────┴─────────┐
              │ 就绪任务 > 0 ?     │
              └───┬───────────┬───┘
                否 │           │ 是
                   │           ▼
                   │   ┌───────────────┐
                   │   │  按优先级排序   │
                   │   │  (priority +   │
                   │   │   agent_load)  │
                   │   └───────┬───────┘
                   │           │
                   │           ▼
                   │   ┌───────────────┐
                   │   │  波次并行控制   │
                   │   │  max_parallel  │
                   │   └───────┬───────┘
                   │           │
                   │           ▼
                   │   ┌───────────────┐
                   │   │ 分配 Agent     │
                   │   │ 启动 run_task  │
                   │   └───────┬───────┘
                   │           │
                   └───────────┤
                               │
                               ▼
         ┌─────────────────────────────┐
         │  检查是否所有任务终态？       │
         │  (completed/failed/aborted) │
         └───────┬──────────────┬──────┘
               否 │              │ 是
                 │              ▼
                 │     ┌───────────────┐
                 │     │ 项目完成判定    │
                 │     │ (关键路径?)    │
                 │     └───────────────┘
                 │
                 ▼
           进入下一轮调度
```

### 4.7 Agent 交互时序图

```
 框架侧 (Kernel)                      Agent 侧 (CLI)
      │                                     │
      │  1. 构造 InteractionRequest         │
      │     (kind + intent + spec)          │
      │────────────────────────────────────▶│
      │                                     │
      │  2. Agent 接收任务                  │
      │     - 理解任务意图                  │
      │     - 调用 Skill/MCP 工具           │
      │     - 执行具体工作                  │
      │     - 撰写交付物                    │
      │                                     │
      │  3. Agent 自评 (Quality)            │
      │     - 6 维度打分                    │
      │     - known_gaps 声明               │
      │     - evidence 列举                 │
      │                                     │
      │  4. 调用 submit_result.py           │
      │     - 本地校验 Pydantic 契约        │
      │     - 本地校验 Gate 格式            │
      │     - 原子写入 .response 文件       │
      │────────────────────────────────────▶│
      │                                     │
      │  5. 框架侧 Gate 校验                │
      │     - 契约校验（强类型）            │
      │     - 格式门禁（章节/防 Stub）      │
      │     - 证据门禁（URL/截图）          │
      │     - 代码项目门禁（目录结构）      │
      │                                     │
      │       ┌─ 通过 ──▶ completed         │
      │       │                             │
      │       └─ 失败 ──▶ 生成 feedback     │
      │                重试 / triage        │
      │                                     │
      │  6. 可选：Peer Review               │
      │     - 创建 review 任务              │
      │     - reviewer Agent 评审           │
      │     - passed / feedback             │
      │                                     │
      │  7. POST 沉淀（异步）               │
      │     - Ledger 写入 KB                │
      │     - Lesson 写入教训库             │
      │     - skill_review 触发             │
      │     - 质量画像更新                  │
```

---

## 五、Agent 内执行质量保证

### 5.1 设计理念

> **单个 Agent 的执行质量，本身也是一个微型 Workflow**

框架不仅在多 Agent 编排层面有 DAG + Gate + Loop，在单个 Agent 执行单个任务时，也有一套类似的质量保证机制——PRE 注入 → 执行 → 自检 → Gate → POST 沉淀。

这形成了一个**嵌套的质量体系**：
```
项目级 Workflow（多 Agent DAG + Gate + Loop）
    └─ 任务级 Harness（单 Agent PRE + Gate + POST）
            └─ Agent 内（自评 + 方法论遵循）
```

### 5.2 五层质量防御体系

#### Layer 0：PRE 执行前注入

**产品提供的能力**：
- 有界 Identity 同步（USER.md / MEMORY.md 字符上限）
- Umbrella Skill 注入（task_type → 方法论 Skill 映射）
- 同类任务经验注入（从 KB 召回历史经验）
- 同类任务教训注入（从 KB 召回历史教训）
- 工作记忆 (L1) 注入
- 用户偏好注入
- 知识库 (L3) Top-K 注入
- Rubric 评分标准告知（产品类任务）

**用户配置的部分**：
- Umbrella Skill 映射关系（`task_type_skills.yaml`）
- 偏好内容（`preferences/`）
- 知识库内容（KB 条目）
- Skill 内容（`business/skills/`）
- Rubric 评分标准（可配置扩展）

**验证方式**：
- 执行前 prompt 中包含所有预期注入块
- 注入内容与配置一致
- 有界 Identity 不超过字符上限

#### Layer 1：Agent 侧自约束

**产品提供的能力**：
- Worker 两阶段响应模板（evaluate → execute）
- Quality 自评模型（score + known_gaps + notes）
- submit_result 本地契约校验（三道关卡）
- Skill 使用纪律（先 Read 全文再执行，禁止臆造）

**用户配置的部分**：
- Worker 规则内容（`worker-template.md`）
- Skill 方法论内容
- 任务验收标准（acceptance_criteria）

**验证方式**：
- 所有 execute 响应都有 quality 字段
- submit_result 非法响应被拦截
- Agent 执行前会 Read 指定的 SKILL.md

#### Layer 2：Gate 确定性门禁

（详见 4.2.3 节）

**核心原则**：只判有没有（客观），不判好不好（主观）。

#### Layer 3：Peer Review 同行评审

（详见 4.2.4 节）

#### Layer 4：POST 执行后沉淀

**产品提供的能力**：

| 能力 | 说明 | 验证方式 |
|------|------|---------|
| **Ledger 沉淀** | 任务成功后将 ledger 写入 KB references/ | 任务成功后 KB 中有对应条目 |
| **Lesson 提取** | 有重试的任务自动提取教训写入教训库 | 重试后任务的教训被记录 |
| **质量画像** 🟡 | 记录 Agent 质量指标到 KB，形成能力画像（数据有记录，未闭环用于分配优化） | Agent 的历史表现可被查询和统计 |
| **Rubric 评估** 🟡 | 6 维度自动化质量评分（辅助，不阻塞，当前仅覆盖产品类任务） | 任务完成后有 rubric 评分报告 |
| **Skill 后台评审** 🟡 | 异步提取 Skill 补丁，写入 _pending/ 待审批（机制完整但不可观测） | 任务完成后有 skill_review 交互记录 |
| **自评估** | 四维度量化评测（产出质量/资产复用/偏好执行/执行效率） | 有完整的 eval 报告 |
| **自改进闭环** 🟠 | 未达标时分级补强，最多 3 轮迭代（框架已搭，未端到端打通） | 低质量任务触发自动补强 |

**用户配置的部分**：
- Skill 评审开关与参数
- Rubric 评分维度和权重（可扩展）
- 自改进基线分数

### 5.3 质量信号整合

| 质量信号 | 来源 | 用途 |
|---------|------|------|
| Gate 是否通过 | Gate 门禁 | 硬门槛，决定任务是否通过 |
| 自评分数 | Agent Quality.score | 参考，触发 needs_review |
| 自评缺陷 | Agent Quality.known_gaps | 触发 needs_review，指导评审 |
| 评审结论 | Peer Review.passed | 确认质量，影响最终状态 |
| 评审意见 | Peer Review.feedback | 指导改进 |
| Rubric 评分 | 自动化评估 | 质量画像、趋势分析 |
| 重试次数 | attempts | 难度指标、质量反向指标 |
| Gate 失败模式 | classified_failures | 问题分类、定向改进 |

---

## 六、知识与经验沉淀

### 6.1 知识库（L3 长期记忆）

> 🟡 基本达标：Protocol 抽象完整，但存储与 L1 耦合，部分 API 绕过抽象层

**产品提供的能力**：
- 统一的 KnowledgeBackend Protocol（可插拔后端）
- SQLite 内置后端（FTS5 全文检索）🟠（与 L1 共用 memory 表，存储耦合）
- 可选 gbrain / 其他外部 KB 后端
- 结构化条目支持（按 task_type 模板分节）
- Tag 分类 + 全文检索
- 按 project_id / task_type 过滤
- 自动写入（任务成功后 Ledger 沉淀）

**用户配置/提供的内容**：
- 知识库内容（团队知识、最佳实践、行业资料）
- KB 模板（各 task_type 的结构化 sections）
- 选择 KB 后端（sqlite / gbrain / 其他）

**验证方式**：
- 写入后可通过 search 检索到
- 任务成功后自动产生 KB 条目
- 切换后端后 API 行为一致

### 6.2 偏好库

**产品提供的能力**：
- 统一的 PreferenceBackend Protocol
- 多后端实现（static / sectioned / mem0）
- 分节管理（style / avoid / principles / tools）
- 全局偏好 + 按 Agent 同步
- 有界注入（字符上限，防止膨胀）
- REST API CRUD

**用户配置/提供的内容**：
- 用户偏好内容（风格、禁忌、工具偏好等）
- 偏好分节定义（`preference_sections.yaml`）
- 偏好后端选择

**验证方式**：
- 修改偏好后，下次对话/任务中体现
- 偏好正确同步到各 Agent workspace
- 注入不超过字符上限

### 6.3 工作记忆（L1 短期记忆）

**产品提供的能力**：
- 统一的 AgentMemoryProvider Protocol
- 多后端实现（sqlite / mem0 / native / noop）
- 按 scope 隔离（agent + mode + group/project）
- before_turn 召回 + after_turn 写入
- 自动降级（高级后端不可用时回退 sqlite）

**用户配置/提供的内容**：
- 选择 L1 后端
- 配置记忆策略（保留多久、多少条）

### 6.4 经验账本 (Ledger)

**产品提供的能力**：
- Ledger 骨架（worked / failed / pitfalls / sources / summary）
- 自动提炼与写入 KB
- 同类任务经验自动注入
- 优先提取 pitfalls / lessons 行
- references/ 目录管理（同类任务沉淀）

**用户配置/提供的内容**：
- Ledger 模板结构
- 是否启用经验沉淀
- 经验注入的条数和策略

### 6.5 Skill 自进化

> 🟡 基本达标：三级沉淀机制完整，但 skill_review 不可观测、自改进闭环未端到端打通。详见 UPGRADE-GAP-ASSESSMENT §2.3 / §2.4.5

**产品提供的能力**：
- 后台 skill_review 交互机制
- 三级沉淀策略（patch → reference → create）
- _pending/ 审批机制（默认开启）
- Skill 安装/卸载/分类/分组
- GitHub 安装支持
- Skill 组机制（批量挂载）

**用户配置/提供的内容**：
- Skill 内容（SKILL.md）
- Skill 目录和分类（catalog.yaml / categories.yaml）
- Skill 与 Agent 的挂载关系
- 是否启用自动 Skill 评审
- 审批 _pending/ 中的 Skill 补丁

### 6.6 质量画像

**产品提供的能力**：
- Agent 跨任务质量追踪
- 多维度指标（通过率、自评、评审、重试次数）
- 按 task_type 分类统计
- 基线对比与趋势分析

**用户配置/提供的内容**：
- 质量基线阈值
- 哪些指标纳入画像

---

## 七、群组协作

### 7.1 群组 notify 模式

**产品提供的能力**：
- @ 具体 Agent，多 Agent 并发响应
- 群消息 SSE 广播
- 群消息历史记录
- 成员管理（增删改序）

**用户配置/提供的内容**：
- 群成员列表
- 群名称和描述

### 7.2 圆桌讨论模式

**产品提供的能力**：
- 6 阶段状态机（独立思考 → 立论 → 主持汇总 → 对齐 → 草案 → 投票）
- 主持人角色（默认 main，可配置）
- 多轮循环 + 分歧交锋
- 共识投票机制（严格多数 + 法定人数）
- Transcript 增量落盘
- 上下文压缩（防止爆炸）
- 最佳实践草案输出
- 共识自动写入 KB（可选）

**用户配置/提供的内容**：
- 最大轮数
- 主持人选择
- 参与率阈值
- 超时设置

### 7.3 项目协作群

> 🟡 基本达标：功能完整，但 project_service 仍读 task_data.json 旧路径

**产品提供的能力**：
- 项目启动自动建群
- 自动添加项目成员
- 进度通报（任务开始/完成/失败）
- 群与项目双向绑定 🟡（旧路径待清理）

**用户配置/提供的内容**：
- 是否启用项目群
- 群名前缀
- 是否包含 main
- 是否启用群讨论对齐

---

## 八、可观测性

### 8.1 产品提供的能力

| 能力 | 说明 | 验证方式 |
|------|------|---------|
| **项目仪表盘** | 状态/进度/成本/任务列表总览 | 页面展示正确的项目数据 |
| **任务 DAG 可视化** | 图形化展示任务依赖和状态 | DAG 图与实际任务状态一致 |
| **执行时间线** | 任务和交互的时间线视图 | 时间线与事件顺序一致 |
| **实时事件流** | SSE 推送项目执行事件 | 执行过程中 UI 实时更新 |
| **交互详情** | 单次交互的完整事件流 | 能看到每个交互的 thinking/tool_use/text |
| **成本分析** | 按任务/Agent 拆分的 token 消耗 | 成本数字与计量结果一致 |
| **Gate 失败详情** | 门禁失败的具体规则和原因 | 失败原因清晰可追溯 |
| **交付物预览** | 在线查看交付物内容 | 能正确渲染 Markdown 交付物 |
| **审计日志** | 操作记录可查询 | 关键操作有审计记录 |
| **质量画像** | Agent 能力趋势图 | 质量数据可追溯 |

### 8.2 用户配置的内容

- 可观测性展示的字段和维度
- 是否启用详细日志
- 数据保留策略

---

## 九、产品成功指标

### 9.1 功能完备性指标

| 指标 | 目标 | 验证方法 |
|------|------|---------|
| Task Type 覆盖数 | ≥ 12 种内置类型 | 统计 templates.yaml 中的 task_type 数量 |
| 内置 Workflow 数 | ≥ 8 个 | 统计 business/workflows/ 中的 workflow 数量 |
| 内置 Skill 数 | ≥ 15 个 | 统计 business/skills/ 中的 Skill 数 |
| 支持的 CLI 后端数 | ≥ 3 个（opencode/claude/Codex） | 验证各后端可正常运行 |
| Gate 检查规则数 | ≥ 8 类 | 统计 gate.py 中的检查规则 |
| Loop 支持格式 | v1 + v2 | 两种格式都能正确运行 |

### 9.2 质量保证指标

| 指标 | 目标 | 验证方法 |
|------|------|---------|
| Gate 通过率（标准任务） | ≥ 85% | 统计回归测试的 Gate 通过率 |
| 重试后最终通过率 | ≥ 95% | 3 次重试后的任务通过率 |
| Peer Review 检出率 | ≥ 30% | review 发现问题的比例 |
| 经验沉淀覆盖率 | ≥ 70% | 成功任务中有 ledger 沉淀的比例 |
| Skill 评审触发率 | ≥ 50% | 成功任务中触发 skill_review 的比例 |

### 9.3 可靠性指标

| 指标 | 目标 | 验证方法 |
|------|------|---------|
| 断点续跑成功率 | 100% | 随机中断后恢复，状态正确 |
| 看门狗有效率 | 100% | 模拟卡死场景，看门狗能正确超时重试 |
| 并发数据一致性 | 无脏数据 | 并行执行后数据完整性检查 |
| 长任务稳定性（8h+） | 无崩溃 | 长时间运行测试 |

### 9.4 可扩展性指标

| 指标 | 目标 | 验证方法 |
|------|------|---------|
| 新增 task_type | 只改配置不改代码 | 新增一个 task_type 并验证可用 |
| 新增 CLI 后端 | 新增 adapters/ 目录即可 | 新增一个 stub 后端并验证可切换 |
| 新增 Skill | 新增目录 + 注册即可 | 新增一个 Skill 并验证可挂载 |
| 新增 KB 后端 | 实现 Protocol 即可 | 新增一个 KB 后端并验证可切换 |

### 9.5 测量协议（度量基准集）

> 指标如果没有固定的测量方法和基准集，就无法长期对比，也无法判断是进步了还是退步了。
> 本节定义一套**固定的度量集**，所有版本升级前后都用同一套测试用例测量，确保可比性。

#### 9.5.1 基准测试集（Benchmark Suite）

| 测试集 | 用例数 | 覆盖维度 | 运行方式 | 基准版本 |
|--------|--------|---------|---------|---------|
| **Gate 基准集** | 20 个用例 | 格式门禁、契约门禁、证据门禁、防 Stub | pytest backend/common/tests/test_gate.py | v1.0 基线 |
| **Process 基准集** | 10 个用例 | DAG 调度、状态转换、重试、triage | pytest backend/common/tests/test_process.py | v1.0 基线 |
| **Workflow 基准集** | 5 个用例 | v1 loop、v2 loop、多 body 分支 | pytest backend/common/tests/test_workflow*.py | v1.0 基线 |
| **端到端基准集** | 3 个用例 | 完整项目运行（简单文档/中等调研/复杂产品） | run_kernel.py 固定 goal | v1.0 基线 |
| **质量基准集** | 5 个用例 | Rubric 评分一致性、review 检出率 | 固定交付物 + 固定 reviewer prompt | v1.0 基线 |

#### 9.5.2 测量方法规范

**Gate 通过率测量：**
```
测量对象：固定 20 个 Gate 测试用例集
通过标准：Gate.validate() 返回 success=True
测量频率：每次发版前
数据记录：
  - gate_pass_rate = passed / total
  - gate_pass_rate_by_kind = {markdown: x%, code_project: y%, ...}
  - gate_retry_effectiveness = 第N次重试通过率
```

**端到端成功率测量：**
```
测量对象：固定 3 个项目 goal
  1. 简单文档任务（写一份产品功能介绍）
  2. 中等调研任务（竞品分析报告）
  3. 复杂产品任务（PRD 撰写 + 评审 + 修改）
通过标准：
  - 项目状态 == completed
  - 所有 Gate 检查通过
  - 无运行时错误
测量频率：每月 / 每次大版本
数据记录：
  - e2e_success_rate = completed / total
  - avg_cycles_per_task = 总轮次 / 任务数
  - avg_gate_retries = Gate 重试总次数 / 任务数
```

**质量测量：**
```
测量对象：固定 5 份交付物 + 固定 reviewer prompt
评分维度：
  - Rubric 6 维度分（完整性/准确性/结构/深度/表达/合规）
  - Review 检出问题数
  - 自评 vs 评审一致性
测量频率：每月
数据记录：
  - rubric_avg_score = 6 维度平均分
  - review_issue_count = 评审发现问题数
  - self_review_correlation = 自评与评审分的相关系数
```

#### 9.5.3 数据采集规范

| 数据项 | 采集位置 | 存储位置 | 粒度 |
|--------|---------|---------|------|
| Gate 检查结果 | gate.py validate() | run_event 表 | 每次 Gate 检查 |
| 任务状态变更 | process.py run_task() | task 表 + run_event | 每次状态变更 |
| Token 使用量 | agent_port.py | project 表 + task 表 | 每次交互 |
| 评审结果 | review kind 处理 | run_event 表 | 每次评审 |
| Ledger 沉淀 | post/ledger.py | memory 表（kind=ledger） | 每次任务完成 |
| Skill 评审 | skill_review daemon | skill_pending 表 | 每次触发 |
| 重试次数 | process.py | task 表 retries 字段 | 每次重试 |

#### 9.5.4 版本对比模板

每次版本发布填写以下对比表：

```
版本对比：vX.Y → vX.Z
测量日期：YYYY-MM-DD
基准版本：v1.0

| 指标 | v1.0 基线 | vX.Y | vX.Z | 变化幅度 | 是否达标 |
|------|----------|------|------|---------|---------|
| Gate 通过率 | 85% | xx% | xx% | ±x% | ✅/❌ |
| 端到端成功率 | - | xx% | xx% | ±x% | ✅/❌ |
| 平均重试次数 | - | x.x | x.x | ±x.x | - |
| Review 检出率 | 30% | xx% | xx% | ±x% | ✅/❌ |
| Ledger 覆盖率 | 70% | xx% | xx% | ±x% | ✅/❌ |
| 新增 task_type 成本 | - | x天 | x天 | ±x天 | - |
| 断点续跑成功率 | 100% | xx% | xx% | - | ✅/❌ |

备注：（环境变化、模型变化等影响因素）
```

#### 9.5.5 注意事项

1. **基准集一旦固定，不轻易修改**：修改基准集需要记录变更原因和新旧对比
2. **模型版本固定**：测量时使用相同的模型和参数，排除模型因素干扰
3. **温度参数固定**：temperature=0 或固定值，减少随机性
4. **多次测量取均值**：质量类指标至少跑 3 次取平均值
5. **环境快照**：每次测量记录模型版本、依赖版本、配置文件版本

---

## 十、v1.x 不做什么（边界声明）

> 明确的边界和明确的范围同样重要。以下是 v1.x 版本**明确不做**的事情，避免范围蔓延。

### 10.1 不做模型层

| 不做什么 | 说明 | 为什么不做 |
|---------|------|-----------|
| 不做模型训练/微调 | myteam 不训练任何模型，只调用外部模型 API | 模型训练是独立赛道，myteam 定位是协作框架 |
| 不做模型路由/负载均衡 | 不对多模型做智能路由和负载均衡 | 各 CLI 后端（opencode/claude/Codex）自己管模型选择 |
| 不做 Prompt 优化服务 | 不提供自动优化 Prompt 的服务 | Prompt 是配置内容，由用户/Agent 自行优化 |

### 10.2 不做基础设施层

| 不做什么 | 说明 | 为什么不做 |
|---------|------|-----------|
| 不做容器化部署 | 不提供 K8s/Docker 部署方案 | v1.x 面向单机/小团队，部署方案交给用户 |
| 不做多租户隔离 | 不做组织/团队/权限的多租户体系 | v1.x 是单团队使用，多租户是 v3+ 考虑 |
| 不做高可用集群 | 不做主从/集群/分片 | SQLite 单机够用，分布式是 v3+ 考虑 |
| 不做 CI/CD 集成 | 不内置 GitOps/流水线 | 作为外部工具通过 MCP 接入，不由内核提供 |

### 10.3 不做业务层

| 不做什么 | 说明 | 为什么不做 |
|---------|------|-----------|
| 不做内置业务 Skill | 不绑定特定行业/领域的 Skill 内容 | 业务 Skill 是用户配置，框架只提供机制 |
| 不做内置 Agent 角色 | 不强制角色分工（产品/研发/测试...） | 角色定义在 agents_registry.json，用户完全可配 |
| 不做内置 Workflow 模板 | 不提供行业标准化 Workflow | Workflow 是策略层内容，由用户/业务层提供 |
| 不做交付物质量评估服务 | 不对交付物做主观打分 | 质量评估是 Gate + Rubric + Review 的组合结果，不由单一服务决定 |

### 10.4 不做的交互形态

| 不做什么 | 说明 | 为什么不做 |
|---------|------|-----------|
| 不做移动端 App | 只有 Web Hub，不做 iOS/Android | v1.x 聚焦桌面端工作场景 |
| 不做语音/视频交互 | 只有文本交互 | 语音视频是独立的交互模态，v1.x 不涉及 |
| 不做实时协同编辑 | 不做多人同时编辑同一文档 | Agent 协作是任务级的，不是文档级协同 |

### 10.5 反模式（设计原则的反面）

以下是产品设计中**刻意避免**的反模式：

1. **不做"智能"黑盒**：所有决策都可追溯、可解释、可配置，没有神秘的"AI 决定"
2. **不做隐式状态**：所有状态变化都有事件记录，不存在框架偷偷改了配置的情况
3. **不做自动修复**：输出不合规 → 拒绝 + 反馈 + 重试，而不是框架悄悄帮你改对
4. **不做魔法约定**：所有配置都有显式声明，不靠目录名/文件名的隐式约定
5. **不做单点失败**：任何一个 Agent 挂掉都不影响整个系统，有重试/降级/人工接管

---

## 十一、版本路线图

### v1.0（当前基线）
- ✅ 私聊 + 群组 + 圆桌讨论
- ✅ Workflow DAG 编排
- ✅ Gate 形式化门禁
- ✅ Triage 失败分诊
- ✅ Loop 循环（v1 + v2）
- ✅ Peer Review 同行评审
- ✅ execution_harness 五层质量防御
- ✅ memstack 知识库/偏好/工作记忆
- ✅ Skill 系统 + 后台评审
- ✅ 可观测性 API + 前端仪表盘

### v1.1（边界澄清）
- 🔲 协调者角色配置化
- 🔲 code_project 驱动配置化
- 🔲 PGD 严格类型配置化
- 🔲 Agent 显示名统一从 registry 读取
- 🔲 Prompt 配置 UI 管理

### v1.2（三库独立）
- 🔲 偏好库独立服务
- 🔲 知识库独立存储层
- 🔲 项目库轻独立（统一接口 + 清理旧路径）
- 🔲 打破 harness-memstack 双向依赖

### v2.0（架构升级）
- 🔲 代码结构重组（common/ 子目录拆分）
- 🔲 配置管理层统一
- 🔲 质量信号统一看板
- 🔲 质量反馈驱动任务分配优化
- 🔲 A/B 测试框架

### 与升级路线图的对应关系

> 产品版本节点与 [UPGRADE-GAP-ASSESSMENT.md](./UPGRADE-GAP-ASSESSMENT.md) 的 Phase 划分对齐关系：

| PRODUCT 版本节点 | 对应 UPGRADE Phase | 关键交付 |
|----------------|-------------------|---------|
| v1.0（当前基线） | — | 现有能力快照 |
| v1.1（边界澄清） | Phase 0 | 协调者/code_project/PGD/显示名配置化；KB API 走抽象层；旧 project_service 路径清理 |
| v1.2（三库独立） | Phase 1 | 偏好库/知识库/项目库独立；harness-memstack 双向依赖打破 |
| v2.0（架构升级） | Phase 2 + Phase 3 | common/ 子目录拆分；server.py 端点拆分；质量闭环打通 |
| v2.x（体验完善） | Phase 4 | 127 项配置 UI 全覆盖 |

---

## 附录 A：产品能力 vs 用户配置能力速查表

| 能力 | 产品提供 | 用户配置 | 配置载体 |
|------|---------|---------|---------|
| DAG 调度算法 | ✅ | - | - |
| 任务 DAG 内容 | - | ✅ | workflow YAML |
| Gate 检查算法 | ✅ | - | - |
| Gate 检查规则（检查什么章节） | - | ✅ | templates.yaml |
| Interaction 契约结构 | ✅ | - | - |
| 验收标准内容 | - | ✅ | acceptance_criteria |
| Skill 挂载机制 | ✅ | - | - |
| Skill 具体内容 | - | ✅ | SKILL.md |
| 圆桌讨论流程 | ✅ | - | - |
| 圆桌成员和议题 | - | ✅ | 群配置 + 用户输入 |
| Loop 循环机制 | ✅ | - | - |
| 循环条件和轮数 | - | ✅ | workflow.loops |
| Token 计量机制 | ✅ | - | - |
| 预算金额 | - | ✅ | CLI 参数 / 配置 |
| 质量评分算法 | ✅ | - | - |
| 质量评分维度和权重 | - | ✅ | rubric 配置 |
| 经验沉淀机制 | ✅ | - | - |
| 经验内容 | - | ✅ | KB 条目 + Ledger |
| MCP 协议支持 | ✅ | - | - |
| MCP 具体服务 | - | ✅ | mcp_registry.json |
| 可观测性框架 | ✅ | - | - |
| 展示维度和字段 | - | ✅ | 前端配置 |
