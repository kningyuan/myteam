---
name: myteam 用户手册
description: myteam 多 Agent 协作平台的完整使用指南，覆盖设计理念、代码实现、全部功能页面和编排内核业务流程。适用于平台使用者和运维者。
---
# myteam 用户手册

> **适用**：myteam 平台使用者、运维者、新成员入门。
> **不适用**：内核代码修改（用 `coordination-methodology`）、领域交付方法论（用各角色 `*-methodology`）。

---

## 何时使用本 Skill

- 新成员需要了解 myteam 平台全貌
- 查找某个功能页面的操作方式
- 理解编排内核的执行流程（goal → DAG → 交付）
- 确认配置项、task_type、delivery_profile 的含义
- 排查项目执行、Agent 管理、Skill 挂载等问题

---

## 1. myteam 是什么

myteam 是一个轻量级**多 Agent 协作平台**。它把"一个目标自动拆解成任务 DAG、调度多个 AI Agent 协同完成、经确定性门禁验收、最终交付结构化产物"这件事，变成可运行、可观测、可重试的工程流程。

核心价值：
- 用声明式内核（而非一个大 Skill）管理多 Agent 协作，调度/门禁/重试/审计/持久化做成系统级基础设施
- 通过适配器隔离，Agent 底层 CLI 可以是 opencode 或 Claude Code，切换后端不需要改 UI 和服务层

### 两条正交执行流

| 流程 | 定位 | 入口 |
|------|------|------|
| **Hub 交互流** | 人 ↔ Agent 实时对话（私聊/群聊/管理/可观测） | `./run.sh start` → `http://localhost:8765/v2/` |
| **编排内核流** | goal → 任务 DAG → 多 Agent 自动交付 | `run_kernel.py` 或 Hub 创建项目 |

两条流共用 Agent 名册、Skill/MCP 挂载和 SQLite 真相库，但进程独立、互不阻塞。可同时运行。

### 三层系统设计

| 层 | 路径 | 职责 | 判断规则 |
|----|------|------|----------|
| **System Kernel** | `backend/common/`、`backend/adapter/` | Process、AgentPort、Gate、Store、contracts | 失败会污染系统状态 → Kernel |
| **Strategy Registry** | `business/templates/`、`business/config/` | task_type、prompt 壳、名册、验收规则 | 改 task_type / 角色 / 验收 → Registry |
| **Skill Pack** | `business/skills/` | 具体执行方法论 | 只影响单次任务质量 → Skill |

**关键规则**：新增 task_type 必须先改 `business/templates/templates.yaml`，只写 Skill 无法让 Process 识别任务。

---

## 2. 设计方案

### 编排内核架构（四个核心组件）

- **Process**：状态机驱动器（team_config → task_plan → wave 调度 → execute → gate → review → finalize）
- **AgentPort**：Interaction 投递与回收，同步阻塞，两段式看门狗（soft_idle 120s / hard_idle 300s）
- **Gate**：确定性验收，只判契约 + 格式 + 完整性（客观/可复现/阻塞），不判质量
- **Store**：SQLite 真相库（project / task / interaction / run_event / memory）

### 交互契约模型

框架与 Agent 之间只交换一对 Pydantic 模型：`InteractionRequest` / `InteractionResponse`，用 `kind` 做辨识联合。

| kind | 用途 | 关键产出 |
|------|------|---------|
| `team_config` | 组队决策 | agents 名册 |
| `task_plan` | 任务拆分 | tasks DAG |
| `evaluate` | 派发前评估 | should_split / sub_tasks |
| `execute` | 执行任务 | outcome + quality 自评 |
| `plan` | 预执行规划 | approach / steps / risks |
| `review` | 同行评审 | passed / feedback |
| `triage` | 失败分诊 | retry/reassign/drop/abort/split |
| `skill_review` | Skill 复盘 | patch/reference/create/noop |

### 适配器隔离（核心不变量）

- `adapters/<cli>/parser.py` 是唯一允许知道 CLI 原始输出格式的地方
- 服务层不得包含 `opencode` 或 `subprocess`
- UI 不得引用 CLI 专属字段，只消费 `thinking` SSE 事件的 `type`
- 新增 CLI = 新建 `adapters/<cli>/` + parser，无需改 UI

### 关键设计决策

| 决策 | 含义 |
|------|------|
| D1/F1 | 非法输出被拒绝而非抢救，无 JSON 修复路径 |
| D7 | 两段式看门狗：soft_idle 疑似卡死 / hard_idle 取消+重试 |
| D8 | 幂等治理：按 interaction_id 命名；启动对账 GC |
| D11 | 结构进代码、内容约束进配置；execute/review 强制 quality 自评 |
| D13 | 运行态状态 = SQLite（真相） |
| D14 | Gate 只判契约 + 格式 + 完整性；质量归 Agent |
| D18 | failed（阻塞）vs needs_review（不阻塞）；重试耗尽 → triage |

### 框架冻结

L1/L2 内核 + Hub 已冻结。新能力去 `business/workflows/` 和 `business/skills/`，不做内核重构。

---

## 3. 快速开始

### 启动 Hub

```bash
cd /path/to/myteam
./run.sh start
# 浏览器访问 http://localhost:8765/v2/
./run.sh stop
```

### 运行编排内核

```bash
export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend" NO_PROXY="localhost,127.0.0.1,::1"
venv/bin/python3 backend/common/run_kernel.py <project_id> \
  --goal "分析2026年主流AI编程助手的竞争格局" \
  --mode one_shot --budget 150000 --review

# Claude Code 后端
venv/bin/python3 backend/common/run_kernel.py <project_id> \
  --goal "..." --backend claude --budget 150000

# 断点续跑
venv/bin/python3 backend/common/run_kernel.py <project_id> --resume
```

CLI 参数：`--goal`（必填）、`--mode one_shot|recurring`、`--budget`、`--max-cycles`、`--review`、`--split`、`--backend opencode|claude`、`--workflow`、`--resume`。

---

## 4. 功能页面操作指南

### 总览仪表盘（/）

统计卡片（项目数/群组数/Agent数/Token消耗）、快捷入口、最近项目列表。空状态提供初始化 Agent、运行 Demo、创建项目。

### 私聊对话（/chat/:agentId）

- 左侧 Agent 列表（搜索 + 归档恢复）
- SSE 流式对话，消息上方显示 @agent_id 和时间戳
- 顶栏菜单：Agent 配置（后端/模型）、清空对话、归档对话
- 全局流订阅实时更新左侧"处理中"状态

### 群组协作（/groups/:groupId）

- 新建群组（名称/描述/勾选成员）
- @具体Agent：群聊回复模式（同私聊，展示在群内）
- @all / @everyone：圆桌讨论模式（全员多轮发言 + 主持人汇总对齐）
- 成员管理：添加/移除/调序、设置主持人、设置最大讨论轮数
- 顶栏菜单：成员管理、清空消息、解散群组

### 项目管理（/projects/:projectId）

**创建项目**：名称 + 目标（必填）+ 工作流 + 模式（one_shot/recurring）+ Token预算 + 评审/拆分选项。

**项目详情 5 个 Tab**：

| Tab | 内容 |
|-----|------|
| 概览 | 发起配置、舰队状态、迭代轮次、成本摘要 |
| DAG | 任务依赖图（缩放/拖拽/点击跳交付物） |
| 执行过程 | 质量卡片 + 执行事件树（门禁/评审/预算时间线） |
| 交付物 | 质量卡片 + Markdown 交付物查看 |
| 成本 | Token 预算进度、按 Agent 柱状图、金额折算 |

**操作**：续跑（断点恢复）、取消（停派新任务）、删除（详情面板红色按钮，删全部数据）。

### 独立任务执行（/execute）

单 Agent execute 质量验证，不走 Workflow。prepare → Agent 填交付物 → finish 沉淀到 KB。4 个 Tab：Harness / Prompt / 交付物 / Ledger。

### Skill 库（/skills）

- 分类与 Skill 同级展示，按修改时间排序
- 新建分类（id + 显示名）、删除分类（仅移除标签）
- Skill 详情：内容编辑、名称修改、分类移动
- 删除 Skill 同时从所有 Agent 卸载
- 待审批：approve/reject pending skill patch
- Skill 生命周期：项目完成 → auto 抽取草稿 → review 产出 pending → approve 入生产

### MCP 管理（/mcp）

- 新建 MCP（id + 显示名，默认 local + npx 命令）
- 配置：command/url/environment/headers/timeout
- 启用/停用切换
- 删除（同时从所有 Agent 移除挂载）
- Agent 挂载在管理 → Agent 页面勾选，Hub 启动时自动同步

### 工作流编辑（/workflows）

- 表单编辑任务编排（添加/上移/下移/删除步骤）
- AI 推导（输入描述自动推荐结构）
- 选项：review_enabled / split_enabled / parallel_enabled / max_parallel

---

## 5. 管理中心（/manage）

7 个子 Tab：

| Tab | 功能 |
|-----|------|
| **Agent** | 团队成员管理：后端/模型/工作目录/挂载Skill+MCP/人设编辑(IDENTITY.md/SOUL.md)/共享规则/新建/删除/同步 |
| **偏好库** | 团队通用偏好（操作规则与交付标准），注入全员 Agent |
| **知识库** | 任务沉淀经验 CRUD，按 kind 过滤（团队通用/按项目/L1工作记忆） |
| **任务类型** | task_type 定义 CRUD，outcome_kind(artifact/action/code_project)/章节/验收标准，支持 AI 推导 |
| **交付模板** | 结构化交付契约(YAML)，绑定 task_type，支持导入 |
| **Prompt 模板** | 框架与 Agent 交互的 Prompt 编辑（kinds + task_types） |
| **交付流程** | 执行过程工件定义（none/light_v1/all_v1） |

### 交付流程（delivery_profile）详解

| profile | 场景 | 过程产物 |
|---------|------|---------|
| `none` | 简单任务 | 无 |
| `light_v1` | 内容型，需对齐+自检 | align.md + verify.log |
| `all_v1` | 工具型，完整流程 | align.md + plan.md + verify.log + ledger + trace |

task_type 定义"做什么"，delivery_profile 定义"怎么做"。

---

## 6. 系统设置（/settings）

| 配置域 | 内容 |
|--------|------|
| 系统 | 端口、默认后端/模型、CLI 路径 |
| 协作 | 通知开关、项目群绑定 |
| 群配置 | @all 圆桌默认参数 |
| 执行 | 看门狗超时、最大重试、max_gate_retries |
| 项目 | Token 预算、并行上限、split 深度（最大 2 层） |
| 执行质量 | Harness/Memstack 开关、自评 floor |

**重要**：`system.use_sqlite_project_store = true` 必须开启。

---

## 7. 编排内核业务流程

### 完整执行链路

```
goal → team_config(组队) → task_plan(拆DAG) → evaluate(评估拆分)
  → wave调度 → execute(执行) → Gate(门禁验收)
    → 通过 → quality自评 → review?(评审) → finalize(完成)
    → 失败 → retry(重试,max 3次) → 耗尽 → triage(分诊)
      → retry/reassign/drop/abort/split
  → 全部completed → 项目completed
```

### 门禁三类

1. **契约门禁**：响应符合 InteractionResponse 契约
2. **格式/完整性门禁**：必需章节、标题层级、file_exists、防 stub
3. **证据门禁**：action 型需 URL + 截图 + 标题核对

### 失败处理

- Gate 失败 → 自动重试（带 feedback），最多 max_gate_retries 次（默认 3）
- 耗尽 → Main Agent triage 决策：retry / reassign / drop / abort / split
- failed（阻塞依赖者）vs needs_review（不阻塞，默认）

### 预算治理

- ok（<80%）→ alert（≥80%）→ over（≥100%，暂停项目）
- 降级阈值 → 切换轻量 backend/model

### 断点续跑

- 不重跑规划，回收孤儿响应，结算卡住任务
- 从 wave 调度继续，自动跳过 needs_review 任务

---

## 8. 内置 task_type 速查

| task_type | 显示名 | 产出形态 |
|-----------|--------|---------|
| research | 调研 | artifact |
| coding | 编码 | artifact |
| review | 评审 | artifact |
| competitive-analysis | 竞品分析 | artifact |
| product-planning | 产品规划 | artifact |
| product-research | 产品调研 | artifact |
| business-diagnosis | 业务诊断 | artifact |
| data-analysis | 数据分析 | artifact |
| acceptance-report | 验收报告 | artifact |
| decision-record | 决策记录 | artifact |
| code-deployment | 部署上线 | artifact |
| publish-post | 发布帖子 | action |
| code-deliverable | 代码交付 | code_project |

---

## 参考文档

- 完整 HTML 版用户手册：`myteam-user-manual/myteam-user-manual.html`
- 架构文档：`docs/CODE-WIKI.md`
- 项目指导：`AGENTS.md`、`CLAUDE.md`
- 交互契约：`backend/common/contracts.py`
- 内核入口：`backend/common/run_kernel.py`
- task_type 定义：`business/templates/templates.yaml`
- Skill 目录索引：`business/skills/catalog.yaml`
- Skill 分类：`business/skills/categories.yaml`
