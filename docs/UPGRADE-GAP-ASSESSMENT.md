# myteam 差距评估与升级方案

> 版本：v1.0
> 日期：2026-06-26
> 基准产品方案：[PRODUCT-DESIGN.md](./PRODUCT-DESIGN.md)

---

## 一、评估总览

### 1.1 评估方法

基于产品设计方案中的**产品能力清单**，逐项对照 myteam 当前代码库的实际实现，评估差距等级并给出升级路径。

**差距等级定义：**

| 等级 | 符号 | 说明 |
|------|------|------|
| 完全达标 | ✅ | 产品能力已完整实现，且边界清晰 |
| 基本达标 | 🟡 | 核心功能已实现，但有边界模糊或需要优化 |
| 部分实现 | 🟠 | 框架已搭好，但功能不完整或有已知缺陷 |
| 尚未实现 | 🔴 | 产品方案中要求，但当前未实现 |

**升级优先级定义：**

| 优先级 | 说明 | 评估维度 |
|--------|------|---------|
| **P0** | 必须做，影响核心架构边界 | 架构合理性 + 维护成本 |
| **P1** | 应该做，显著提升产品价值 | 用户价值 + 实现成本 |
| **P2** | 可以做，锦上添花 | 长期价值 + 实现成本 |

### 1.2 总体评估结论

| 能力域 | 达标率 | 主要差距 |
|--------|--------|---------|
| 交互式执行（私聊） | 90% | 边界基本清晰，少量硬编码 |
| 编排式交付（Workflow） | 80% | 功能完整，但配置化程度不足 |
| Agent 内执行质量 | 75% | 五层防御体系完整，但自改进闭环未完全打通 |
| 知识与经验沉淀 | 70% | 各模块有雏形，但存储耦合 + 双向依赖 |
| 群组协作 | 85% | 功能完整，配置化程度高 |
| 可观测性 | 80% | 数据完整，展示层可优化 |
| 系统边界清晰度 | 60% | 10+ 处硬编码泄露，是最大的架构债 |
| 配置 UI 覆盖率 | 75% | 32 项配置无 UI，Prompt/交付套餐缺口最大 |

**总体评估：myteam 已实现产品方案中约 80% 的能力，核心架构设计优秀，主要差距在于「边界清晰度」、「模块独立性」和「配置 UI 覆盖率」——功能都有，但"哪些是产品提供、哪些是用户配置"的界线还不够干净，且约 25% 的用户配置项缺少前端管理页面。**

---

## 二、逐项差距评估

### 2.1 交互式执行（Agent 私聊）

| 产品能力 | 当前状态 | 差距等级 | 差距说明 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| 多轮对话记忆 | 已实现 | ✅ | DM 记忆路径完整，滚动摘要 + 召回 | - |
| 全工具权限 | 已实现 | ✅ | interactive 模式下全套工具可用 | - |
| 身份上下文 | 已实现 | 🟡 | 三层身份注入完整，但 Agent 显示名有硬编码 | P1 |
| Skill 工具箱 | 已实现 | 🟡 | Skill 挂载机制完整，但 task_type→umbrella 映射可配置化程度待提升 | P2 |
| MCP 工具集 | 已实现 | ✅ | MCP 协议支持完整 | - |
| 多 Agent 协作感知 | 已实现 | 🟡 | MultiAgentManager 预加载 + 协作上下文，但协作上下文较薄（只有名字+角色） | P2 |
| 对话归档与搜索 | 已实现 | ✅ | 归档 + 搜索功能完整 | - |
| 后台任务不中断 | 已实现 | ✅ | stream_background_on_disconnect 机制完整 | - |

**差距汇总：**
- **显示名硬编码**：`agent_transport.py` 中 `_AGENT_DISPLAY_NAMES` 只覆盖 5 个角色，应统一从 `agents_registry.json` 读取
- **协作上下文偏薄**：只包含名字和角色，缺少能力标签、task_type 范围等信息（不过这是设计选择，不是缺陷）

**升级工作量估算：0.5 天**

---

### 2.2 编排式交付（Workflow 项目）

#### 2.2.1 Workflow 编排引擎

| 产品能力 | 当前状态 | 差距等级 | 差距说明 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| DAG 调度 | 已实现 | ✅ | 拓扑排序 + 波次调度完整 | - |
| 并行执行 | 已实现 | ✅ | parallel_enabled + max_parallel | - |
| 断点续跑 | 已实现 | ✅ | Process.resume() + reconcile_on_start | - |
| 任务状态机 | 已实现 | ✅ | 6 种状态完整 | - |
| 项目状态机 | 已实现 | ✅ | 7 种状态完整 | - |

**结论：完全达标 ✅**

#### 2.2.2 任务拆分与子任务

| 产品能力 | 当前状态 | 差距等级 | 差距说明 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| Evaluate 评估拆分 | 已实现 | 🟡 | 功能完整，但协调者角色硬编码为 "main" | P0 |
| 子任务插入 DAG | 已实现 | ✅ | plan_splice 逻辑完整 | - |
| 层级命名 | 已实现 | ✅ | {parent}.{sub} 命名规范 | - |
| 深度保护 | 已实现 | ✅ | max_split_depth 默认 2 | - |
| 扇出保护 | 已实现 | ✅ | max_subtasks 默认 8 | - |

**差距汇总：**
- **协调者角色硬编码**：`decision_pipeline.py` 中 `agent_id="main"` 多处硬编码，用户无法自定义协调者

**升级工作量估算：1 天**

#### 2.2.3 Gate 形式化门禁

| 产品能力 | 当前状态 | 差距等级 | 差距说明 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| 契约门禁 | 已实现 | ✅ | Pydantic 强校验 | - |
| 格式门禁 | 已实现 | 🟡 | 检查规则完整，但 code_project 类型硬编码列表 | P0 |
| 防 Stub | 已实现 | 🟡 | 占位符标记硬编码（含中文） | P2 |
| 证据门禁 | 已实现 | 🟡 | action 类任务完整，但反爬标记硬编码 | P2 |
| 代码项目门禁 | 已实现 | 🟡 | 功能完整，但 CODE_PROJECT_TASK_TYPES 硬编码 | P0 |
| 自动重试 | 已实现 | ✅ | max_gate_retries + feedback | - |
| 纯格式优化 | 已实现 | ✅ | patch_hint 机制完整 | - |

**差距汇总：**
- **code_project 类型硬编码**：`CODE_PROJECT_TASK_TYPES = frozenset({"code-deliverable", "code-writing", "code-testing"})`，应完全由 `outcome_kind: code_project` 驱动
- **PGD 严格类型硬编码**：`_PGD_STRICT_TYPES` 硬编码 2 种类型，应配置化
- **占位符/反爬标记硬编码**：含中文关键词，应可配置

**升级工作量估算：1 天**

#### 2.2.4 同行评审 (Peer Review)

| 产品能力 | 当前状态 | 差距等级 | 差距说明 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| 评审交互 | 已实现 | ✅ | review kind 完整 | - |
| 评审影响状态 | 已实现 | ✅ | passed → completed，否则 needs_review | - |
| 评审阻塞策略 | 已实现 | ✅ | needs_review_blocks 可配置 | - |
| 评审依据统一 | 已实现 | ✅ | acceptance_criteria 共用 | - |

**结论：完全达标 ✅**

#### 2.2.5 Loop 循环迭代

| 产品能力 | 当前状态 | 差距等级 | 差距说明 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| until 条件循环 | 已实现 | ✅ | v1 格式完整 | - |
| 多 body 分支 | 已实现 | ✅ | v2 格式完整 | - |
| PATCH 模式 | 已实现 | ✅ | 基线复制 + 改稿前缀 | - |
| 基线复制 | 已实现 | ✅ | seed_patch_baseline | - |
| 群讨论对齐 | 已实现 | 🟡 | 功能完整，但依赖 business hook（work_review_alignment.py），耦合方式可优化 | P2 |
| 最小/最大轮数 | 已实现 | ✅ | min_rounds + max_rounds | - |
| 断点恢复 | 已实现 | ✅ | reconstruct_loop_state | - |

**结论：基本达标 🟡**

#### 2.2.6 失败分诊 (Triage)

| 产品能力 | 当前状态 | 差距等级 | 差距说明 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| 5 种分诊决策 | 已实现 | ✅ | retry/reassign/split/drop/abort | - |
| 协调者决策 | 已实现 | 🟡 | 功能完整，但协调者硬编码 "main" | P0 |
| 决策可追溯 | 已实现 | ✅ | 记录在 run_event 中 | - |

**差距汇总：同"任务拆分"，协调者角色硬编码**

#### 2.2.7 预算与成本控制

| 产品能力 | 当前状态 | 差距等级 | 差距说明 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| Token 计量 | 已实现 | ✅ | 全链路计量 | - |
| 预算控制 | 已实现 | ✅ | BudgetExceededError + paused | - |
| 自动降级 | 已实现 | ✅ | _maybe_degrade_budget | - |
| 按任务/Agent 拆分 | 已实现 | ✅ | tokens_grouped | - |

**结论：完全达标 ✅**

**编排式交付总评：基本达标 🟡（80%）**
- 核心功能完整度高
- 主要差距：协调者角色硬编码、code_project 类型硬编码、PGD 严格类型硬编码

---

### 2.3 Agent 内执行质量保证

| 产品能力 | 当前状态 | 差距等级 | 差距说明 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| **PRE 注入层** | | | | |
| 有界 Identity | 已实现 | ✅ | 字符上限 + 同步机制 | - |
| Umbrella Skill | 已实现 | 🟡 | 映射关系在配置文件，但 task_type_skills.yaml 无 UI 管理 | P2 |
| 同类任务经验 | 已实现 | ✅ | KB ledger 召回 + 智能提取 | - |
| 同类任务教训 | 已实现 | ✅ | lesson 标签召回 | - |
| L1 工作记忆 | 已实现 | ✅ | memstack L1 注入 | - |
| 用户偏好 | 已实现 | ✅ | memstack 偏好注入 | - |
| KB Top-K 注入 | 已实现 | ✅ | memstack KB 注入 | - |
| Rubric 评分标准 | 已实现 | 🟡 | 仅覆盖产品类任务，技术/设计类缺失 | P1 |
| **Agent 自约束层** | | | | |
| 两阶段响应 | 已实现 | 🟡 | worker-template.md 有定义，但实际内核中 evaluate/execute 由框架侧驱动，Agent 侧两阶段概念已弱化 | P2 |
| Quality 自评 | 已实现 | ✅ | Pydantic 模型 + 强校验 | - |
| submit_result 校验 | 已实现 | ✅ | 三道关卡 + 原子写入 | - |
| Skill 使用纪律 | 已实现 | ✅ | prompt 中明确要求 | - |
| **Gate 层** | 已实现 | 🟡 | （见 2.2.3） | - |
| **Peer Review 层** | 已实现 | ✅ | （见 2.2.4） | - |
| **POST 沉淀层** | | | | |
| Ledger 沉淀 | 已实现 | 🟡 | 功能完整，但依赖 Agent 填写 ledger 质量 | P2 |
| Lesson 提取 | 已实现 | ✅ | 重试后自动写入 | - |
| 质量画像 | 已实现 | 🟡 | 数据有记录，但未用于任务分配优化 | P1 |
| Rubric 评估 | 已实现 | 🟡 | 6 维度完整，但偏产品类任务 | P1 |
| Skill 后台评审 | 已实现 | 🟡 | 机制完整，但异步执行不可观测 | P2 |
| 自评估 | 已实现 | 🟡 | 四维度量化框架完整 | P2 |
| 自改进闭环 | 部分实现 | 🟠 | 框架搭好，但 Step 2 实际执行是预留钩子，未端到端打通 | P1 |

**差距汇总：**
1. **自改进闭环未完全打通**：`self_improve_loop.py` 是框架级实现，实际执行需要外部传入 deliverable，不能自动端到端运行
2. **Rubric 偏产品类**：6 维度评分和红线机制主要针对产品/调研任务，对编码、设计等任务适配不足
3. **质量画像未闭环**：质量数据有记录，但未反馈到 team_config/task_plan 的 Agent 选择优化
4. **Skill 评审不可观测**：daemon 线程异步执行，失败了也不易发现

**升级工作量估算：3-5 天（自改进闭环是最大项）**

---

### 2.4 知识与经验沉淀

#### 2.4.1 知识库（L3）

| 产品能力 | 当前状态 | 差距等级 | 差距说明 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| KnowledgeBackend Protocol | 已实现 | ✅ | 干净的 Protocol 抽象 | - |
| SQLite 内置后端 | 已实现 | 🟡 | 功能完整，但与 L1 共用 memory 表，耦合 | P1 |
| 外部 KB 后端 | 部分实现 | 🟠 | gbrain 有 adapter 但 pending 状态，未充分验证 | P2 |
| 结构化条目 | 已实现 | ✅ | kb_templates.yaml 定义分节 | - |
| Tag + 全文检索 | 已实现 | ✅ | FTS5 全文检索 + tag 过滤 | - |
| 按 project/task_type 过滤 | 已实现 | ✅ | 支持多维度过滤 | - |
| 自动写入 | 已实现 | ✅ | Ledger 沉淀自动写入 | - |
| 统一 API 入口 | 部分实现 | 🟠 | observability_api 直接调 store.memory_*，绕过 KnowledgeBackend 抽象 | P1 |

#### 2.4.2 偏好库

| 产品能力 | 当前状态 | 差距等级 | 差距说明 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| PreferenceBackend Protocol | 已实现 | ✅ | 干净的 Protocol 抽象 | - |
| 多后端实现 | 已实现 | ✅ | static/sectioned/mem0/user_store | - |
| 分节管理 | 已实现 | ✅ | style/avoid/principles/tools | - |
| 全局 + 按 Agent 同步 | 已实现 | ✅ | user_store 同步机制 | - |
| 有界注入 | 已实现 | ✅ | 字符上限控制 | - |
| REST API CRUD | 已实现 | ✅ | preferences_api.py 完整 | - |

**结论：偏好库独立程度最高，基本达标 🟡（90%）**

#### 2.4.3 工作记忆（L1）

| 产品能力 | 当前状态 | 差距等级 | 差距说明 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| AgentMemoryProvider Protocol | 已实现 | ✅ | 干净的 Protocol | - |
| 多后端实现 | 已实现 | ✅ | sqlite/mem0/native/noop | - |
| 按 scope 隔离 | 已实现 | ✅ | agent + mode + group/project | - |
| before/after_turn | 已实现 | ✅ | 完整的生命周期钩子 | - |
| 自动降级 | 已实现 | ✅ | 不可用时回退 sqlite | - |

**结论：完全达标 ✅**

#### 2.4.4 经验账本 (Ledger)

| 产品能力 | 当前状态 | 差距等级 | 差距说明 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| Ledger 骨架 | 已实现 | ✅ | worked/failed/pitfalls/sources/summary | - |
| 自动提炼写入 KB | 已实现 | 🟡 | 功能完整，但提炼逻辑较简单（关键词匹配） | P2 |
| 同类任务经验注入 | 已实现 | ✅ | PRE 注入阶段自动召回 | - |
| 优先提取 pitfalls | 已实现 | ✅ | _experience_snippet 智能提取 | - |
| references/ 目录管理 | 已实现 | ✅ | 按 skill 组织 references | - |

#### 2.4.5 Skill 自进化

| 产品能力 | 当前状态 | 差距等级 | 差距说明 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| 后台 skill_review | 已实现 | 🟡 | 机制完整，但不可观测 | P2 |
| 三级沉淀策略 | 已实现 | ✅ | patch → reference → create | - |
| _pending/ 审批 | 已实现 | ✅ | 默认开启人工审批 | - |
| Skill 安装/卸载 | 已实现 | ✅ | 完整的 CRUD | - |
| GitHub 安装 | 已实现 | ✅ | 支持远程安装 | - |
| Skill 组机制 | 已实现 | ✅ | 分组 + 批量挂载 | - |

#### 2.4.6 质量画像

| 产品能力 | 当前状态 | 差距等级 | 差距说明 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| 跨任务质量追踪 | 已实现 | 🟡 | 数据有记录，但查询入口不统一 | P2 |
| 多维度指标 | 已实现 | 🟡 | 指标较粗（通过率/自评/重试次数） | P2 |
| 按 task_type 分类 | 已实现 | ✅ | 支持分类统计 | - |
| 基线对比与趋势 | 部分实现 | 🟠 | 有基线概念，但未形成趋势分析能力 | P2 |

**知识与经验沉淀总评：部分实现 🟠（70%）**
- 最大问题：**存储耦合**——KB 和 L1 共用 `store.memory` 表，导致无法独立
- 第二问题：**抽象绕过**——observability_api 直接操作 Store，绕过 KnowledgeBackend
- 第三问题：**双向依赖**——memstack 和 execution_harness 互相调用
- 第四问题：**质量画像未闭环**——有数据但没被使用

---

### 2.5 群组协作

| 产品能力 | 当前状态 | 差距等级 | 差距说明 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| notify 模式 | 已实现 | ✅ | @具体 Agent 并发响应 | - |
| 圆桌讨论 6 阶段 | 已实现 | ✅ | 独立思考→立论→汇总→对齐→草案→投票 | - |
| 主持人角色 | 已实现 | 🟡 | 默认 main，可配置，但选择逻辑硬编码 | P2 |
| 多轮循环 + 分歧交锋 | 已实现 | ✅ | 完整的循环机制 | - |
| 共识投票 | 已实现 | ✅ | 严格多数 + 法定人数 | - |
| Transcript 落盘 | 已实现 | ✅ | 增量 flush | - |
| 上下文压缩 | 已实现 | ✅ | 多层压缩策略 | - |
| 最佳实践草案 | 已实现 | ✅ | BEST_PRACTICE 格式 | - |
| 共识写入 KB | 已实现 | ✅ | on_consensus hook | - |
| 项目协作群 | 已实现 | 🟡 | 功能完整，但 project_group_service 仍读 task_data.json（旧路径） | P1 |
| 进度通报 | 已实现 | ✅ | format_progress_message 统一格式 | - |

**结论：基本达标 🟡（85%）**
- 主要差距：project_group_service 仍读旧版 task_data.json

---

### 2.6 可观测性

| 产品能力 | 当前状态 | 差距等级 | 差距说明 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| 项目仪表盘 | 已实现 | ✅ | DashboardPage + observability API | - |
| 任务 DAG 可视化 | 已实现 | ✅ | ProjectDag 组件 | - |
| 执行时间线 | 已实现 | ✅ | ProjectTimeline + interaction timeline | - |
| 实时事件流 | 已实现 | ✅ | SSE + 签名去抖 | - |
| 交互详情 | 已实现 | ✅ | 完整事件流回放 | - |
| 成本分析 | 已实现 | ✅ | 按任务/Agent 拆分 | - |
| Gate 失败详情 | 已实现 | ✅ | GateFailureList 组件 | - |
| 交付物预览 | 已实现 | ✅ | Markdown 渲染 | - |
| 审计日志 | 已实现 | 🟡 | 有 audit_log 表，但前端展示入口不明显 | P2 |
| 质量画像 | 部分实现 | 🟠 | 数据有记录，但无统一的质量看板页面 | P1 |

**结论：基本达标 🟡（80%）**

---

### 2.7 系统边界清晰度

这是**最大的架构债**，单独列出来评估。

| 边界问题 | 当前状态 | 差距等级 | 影响范围 | 升级优先级 |
|---------|---------|---------|---------|-----------|
| 协调者角色硬编码 | 8+ 处硬编码 "main" | 🔴 | decision_pipeline、process、workflow_loader 等 | P0 |
| code_project 类型硬编码 | 3 处硬编码列表 | 🟠 | project_artifacts、gate.py | P0 |
| PGD 严格类型硬编码 | 1 处硬编码 frozenset | 🟡 | gate.py | P1 |
| Agent 显示名硬编码 | 1 处硬编码 dict | 🟡 | agent_transport.py | P1 |
| 工作流推导模板硬编码 | 多个函数硬编码 | 🟡 | workflow_suggest.py | P2 |
| 身份文件模板硬编码 | 1 处硬编码 dict | 🟡 | agent_bootstrap.py | P2 |
| 规则 profile 映射硬编码 | 3 个常量硬编码 | 🟡 | rules_merge.py | P2 |
| 占位符标记硬编码 | 1 处 tuple 硬编码 | 🟢 | registry.py | P2 |
| 反爬拦截标记硬编码 | 1 处 tuple 硬编码 | 🟢 | gate.py | P2 |
| 代码扩展名硬编码 | 2 处 set 硬编码 | 🟢 | gate.py + project_artifacts.py | P2 |
| 废弃 agent 别名硬编码 | 1 处 dict 硬编码 | 🟢 | agent_id_policy.py | P2 |

**系统边界清晰度总评：60 分（不及格）**
- 这是整个产品最大的架构债务
- 核心问题不是"功能缺失"，而是"边界不清"
- 功能都能工作，但用户很难明确区分"哪些是系统提供的，哪些是我配置的"

---

## 三、三库（知识库/偏好库/项目库）独立评估

### 3.1 独立性评估矩阵

| 维度 | 偏好库 | 知识库 | 项目库 |
|------|--------|--------|--------|
| Protocol 抽象完整性 | ✅ 高 | ✅ 高 | 🟡 中（无独立 Protocol） |
| 存储独立性 | ✅ 高（独立文件 + 同步） | 🟠 低（与 L1 共用 memory 表） | 🟡 中（SQLite 集中但有 Store 门面） |
| API 完整性 | ✅ 高（完整 CRUD） | 🟡 中（API 绕过抽象层） | 🟡 中（新旧双轨） |
| 与内核耦合度 | 🟡 中（同步依赖 agent_registry） | 🟠 高（Store 强依赖） | 🟠 高（Process 强依赖） |
| 可独立测试性 | ✅ 高 | 🟡 中 | 🟡 中 |
| **总体独立可行性** | **极高** | **高（需解耦存储）** | **中高（需清理旧路径）** |

### 3.2 偏好库独立方案

**当前状态：** 几乎已经独立，只差物理位置确认。

**独立路径：**
1. ✅ Protocol 已定义（PreferenceBackend）
2. ✅ 多后端实现已完成
3. ✅ REST API 已提供
4. 🟡 物理位置在 `backend/memstack/preferences/`，可接受
5. ⚠️ 同步机制依赖 `hub.services.agent_registry`，需解耦

**升级工作量：0.5 天（主要是确认边界 + 清理依赖）**

### 3.3 知识库独立方案

**当前状态：** 架构清晰但存储耦合。

**独立路径（3 步）：**

**Step 1：修复抽象绕过（P1）**
- `observability_api.py` 中的 memory CRUD 改走 `KnowledgeBackend` 接口
- `process.py` 中的周期摘要写入改走 KB 后端

**Step 2：存储解耦（P1）**
- 在 memstack 内部定义 `MemoryStore` Protocol
- 将 SQLite 实现内聚到 memstack 内部
- `common/store.py` 作为适配层（委托给 memstack）
- KB 和 L1 可共用底层存储，但通过不同的 Scope 隔离

**Step 3：物理独立（P2）**
- 确认 KB 可作为独立 Python 库发布
- 提供独立的 CLI/API 入口

**升级工作量：2-3 天**

### 3.4 项目库独立方案

**当前状态：** 数据集中在 SQLite，但有新旧双轨问题。

**独立路径（4 步）：**

**Step 1：清理旧路径（P0）**
- `hub/services/project_service.py` 从读 task_data.json 改为读 SQLite
- `hub/services/project_group_service.py` 同上
- 前端 v2 统一走 `/api/obs/*` 新路径

**Step 2：统一 meta schema（P1）**
- 定义 `ProjectMeta` Pydantic 模型，规范 meta JSON 字段
- 各模块通过统一接口读写 meta，不再直接操作 JSON dict

**Step 3：封装项目库模块（P1）**
- 新建 `project_lib/` 或 `common/project/` 目录
- 封装 Store 中所有 project 相关操作
- 封装 project_artifacts、project_admin 等
- 提供统一的项目库 API 门面

**Step 4：交付物元数据（P2）**
- 新增 deliverable 表（SQLite）
- 记录交付物路径、类型、大小、创建时间、版本
- 不再完全依赖文件系统扫描

**留在内核侧的部分：**
- `process.py`（项目执行引擎）
- `project_runtime.py`（进程内调度）
- `project_cancel.py`（取消信号）
- `project_hooks.py`（回调接口）

**升级工作量：4-6 天（Step 1 是最大头）**

---

## 四、配置 UI 覆盖差距评估

> **产品原则：所有用户可配置的内容，必须有对应的前端管理页面。**

### 4.1 总体覆盖情况

| 配置类别 | 配置项数 | 有完整 UI | 有只读 UI | 无 UI | 覆盖率 | 差距等级 |
|---------|---------|----------|---------|-------|--------|---------|
| Agent 相关 | 21 | 12 | 3 | 5 | ~71% | 🟡 |
| Task Type 相关 | 13 | 9 | 1 | 3 | ~77% | 🟡 |
| Workflow 相关 | 9 | 8 | 0 | 1 | ~89% | ✅ |
| Skill 相关 | 13 | 8 | 2 | 3 | ~77% | 🟡 |
| MCP 相关 | 9 | 9 | 0 | 0 | 100% | ✅ |
| 规则相关 | 6 | 5 | 0 | 1 | ~83% | ✅ |
| Prompt 相关 | 2 | 0 | 0 | 2 | 0% | 🔴 |
| 偏好相关 | 4 | 2 | 1 | 1 | 75% | 🟡 |
| 群组相关 | 12 | 10 | 1 | 1 | ~92% | ✅ |
| 系统配置 | 30 | 30 | 2 | 0 | 100% | ✅ |
| 知识库 | 3 | 2 | 0 | 1 | ~67% | 🟡 |
| 其他（PGD/模板等） | 5 | 0 | 0 | 5 | 0% | 🔴 |
| **合计** | **127** | **85** | **10** | **32** | **~75%** | **🟡** |

**结论：当前配置 UI 覆盖率约 75%，距离产品要求的 100% 有明显差距。最大缺口在 Prompt 配置、交付套餐、Agent 注册表编辑等策略层核心配置。**

### 4.2 P0 级缺口（核心业务配置，缺失影响日常使用）

| # | 缺失项 | 配置文件 | 重要性说明 | 建议实现方式 | 工作量 |
|---|--------|---------|-----------|-------------|--------|
| 1 | **Prompt 模板管理** | `business/templates/prompt_templates.yaml` | Prompt 模板是策略层核心，决定 Agent 交互格式和质量 | 在 `/manage/` 下新增「Prompt 模板」tab，按 kind + task_type 分组编辑 | 1.5 天 |
| 2 | **Prompt 注入管理** | `business/templates/prompt_injections.yaml` | Prompt 注入控制交付过程约束，与 delivery_profile 联动 | 与 Prompt 模板合并管理 | 1 天 |
| 3 | **Delivery Profiles（交付等级）管理** | `business/templates/delivery_profiles.yaml` | 决定 light_v1/all_v1 等过程产物套餐，直接影响执行质量 | 在「交付模板」页新增 Profile 管理子视图 | 1 天 |
| 4 | **Agent 注册表编辑** | `business/config/agents_registry.json` | 定义 Agent 角色、能力、可用 task_types，是团队结构基础 | Agent 详情页增加「角色与能力」编辑区 | 1 天 |
| 5 | **task_type_agent_priority 管理** | `business/config/task_type_agent_priority.json` | 控制任务分配优先级，直接影响 DAG 调度结果 | 任务类型详情页增加「执行优先级」配置 | 0.5 天 |

### 4.3 P1 级缺口（提升管理效率，减少手动编辑）

| # | 缺失项 | 配置文件 | 重要性说明 | 建议实现方式 | 工作量 |
|---|--------|---------|-----------|-------------|--------|
| 6 | **知识库模板管理** | `business/config/kb_templates.yaml` | 定义 KB 条目的结构化字段 | 知识库管理页增加「模板设置」 | 0.5 天 |
| 7 | **task_type_skills 映射管理** | `business/config/task_type_skills.yaml` | 控制 execute harness 推荐的 methodology skill | 任务类型详情页增加 Skill 映射配置 | 0.5 天 |
| 8 | **Skill Matrix 审计可视化** | 计算值（catalog × templates） | 帮助发现 Skill 覆盖缺口 | Skill 页增加「覆盖度审计」面板 | 1 天 |
| 9 | **偏好分节管理** | `business/config/preference_sections.yaml` | 定义偏好库的分节结构 | 偏好库页增加分节编辑视图 | 0.5 天 |
| 10 | **Workflow Profiles 管理** | `business/workflows/profiles/*.yaml` | Workflow 扩展点（如 work-review-alignment） | 工作流编辑器中增加 Profile 选择/编辑 | 1 天 |
| 11 | **工作区文件编辑扩展** | `business/workspaces/*/` | AGENTS.md/TOOLS.md/MEMORY.md 等 | Agent 详情页扩大可编辑文件范围 | 0.5 天 |
| 12 | **agent_task_type_rules 管理** | `business/config/agent_task_type_rules.json` | 用于自动任务类型推断 | 任务类型页增加规则编辑器 | 0.5 天 |

### 4.4 P2 级缺口（高级/边缘功能，可延后）

| # | 缺失项 | 配置文件 | 重要性说明 | 建议实现方式 | 工作量 |
|---|--------|---------|-----------|-------------|--------|
| 13 | PGD 默认模型/角色边界管理 | `pgd_default_models.json`, `pgd_role_boundaries.json` | 特定功能配置，使用频率低 | 设置页新增 PGD 子 tab | 0.5 天 |
| 14 | Skill 组（vendor 套件）管理 | 运行时 skill_groups | Skill 分组挂载 | Skill 页增加「组管理」 | 0.5 天 |
| 15 | 业务花名册模板管理 | `business/templates/business-roster.json` | 初始化模板，使用频率低 | 引导流程中配置 | 0.5 天 |

### 4.5 后端 API 缺口分析

前端 UI 依赖后端 API，以下配置项同时缺少后端 API 和前端 UI：

| 配置项 | 后端 API 状态 | 需要新增的 API |
|--------|-------------|--------------|
| Prompt 模板 | 无独立 API | GET/POST/PUT/DELETE `/api/prompt-templates/*` |
| Prompt 注入 | 无独立 API | GET/POST/PUT/DELETE `/api/prompt-injections/*` |
| Delivery Profiles | 无独立 API | GET/POST/PUT/DELETE `/api/delivery-profiles/*` |
| agents_registry 编辑 | 只读 | PUT `/api/agents/registry/{id}` |
| task_type_agent_priority | 无独立 API | GET/PUT `/api/task-types/{id}/priority` |
| kb_templates | 无独立 API | GET/PUT `/api/knowledge/templates` |
| task_type_skills 映射 | 无独立 API | GET/PUT `/api/task-types/{id}/skills` |
| preference_sections | 无独立 API | GET/PUT `/api/preferences/sections` |
| workflow profiles | 无独立 API | GET/PUT `/api/workflows/{id}/profile` |
| agent_task_type_rules | 无独立 API | GET/PUT `/api/task-types/rules` |

---

## 五、代码结构调整差距

### 5.1 目录结构问题

| 问题 | 严重度 | 当前状态 | 目标状态 | 升级优先级 |
|------|--------|---------|---------|-----------|
| common/ 85 个模块平铺 | P0 | 所有 .py 文件在一个目录 | 按功能领域拆分子目录 | P0 |
| server.py 975 行 / 37 端点 | P0 | 端点散落在 server.py 中 | 全部迁移到 routes/ 下 | P0 |
| adapter/ + adapters/ 命名混淆 | P1 | 两个目录只差一个 s | 合并为 adapters/base/ | P1 |
| frontend-v2 命名误导 | P1 | v1 已移除仍叫 v2 | 改名为 frontend/ | P1 |
| base/ 定位不清 | P1 | 不知道是工具类还是业务层 | 移入 hub/domain/ | P1 |
| agentic-workflows 悬停 | P1 | 无代码引用，与 workflows 并列 | 移入 playbooks/ | P1 |
| store/ 目录尴尬 | P2 | 3 个文件分属不同关注点 | 拆分到 config/ + hub/services/ | P2 |
| means/ 命名不直观 | P2 | "手段"语义不清晰 | 并入 skills/ 或改 tools/ | P2 |

### 5.2 功能分布问题

| 问题 | 严重度 | 当前状态 | 目标状态 | 升级优先级 |
|------|--------|---------|---------|-----------|
| Skill 功能分散 5+ 处 | P1 | common/hub/store/adapters/business 都有 | 统一组织：common/skill/ 为核心 | P1 |
| MCP 功能分散 | P1 | 同上 | 统一组织：common/mcp/ 为核心 | P1 |
| Agent 管理横跨 4 个目录 | P1 | base/common/hub/store 都有 | 明确分层：base 并入 hub | P1 |
| 配置管理极度分散 | P1 | 5+ 个目录，10+ 个读取模块 | 统一配置管理层 | P1 |
| 两个 paths.py 重复 | P1 | common/ 和 hub/ 各一份 | 统一到 backend/paths.py | P1 |

### 5.3 命名不一致

| 问题 | 严重度 | 示例 | 升级优先级 |
|------|--------|------|-----------|
| delivery vs deliverable 混用 | P2 | delivery_templates vs deliverable_guarantee | P2 |
| 两个 agent_registry 同名 | P2 | common/ 和 hub/services/ 各一个 | P2 |
| API 路由三种组织方式并存 | P1 | server.py 直挂 / 顶层 api 文件 / routes/ 子目录 | P1 |

---

## 六、升级路线图（可执行、可验证）

### Phase 0：边界澄清（最高优先级，5 天）

> 目标：让"产品提供的能力"和"用户配置的能力"界线清晰

| 序号 | 任务 | 内容 | 验证方法 | 工作量 | 优先级 |
|------|------|------|---------|--------|--------|
| 0.1 | 协调者角色配置化 | 引入 `coordinator_agent_id` 配置，默认 "main"，从 system_config 或 agents_registry 读取；替换所有硬编码 "main" 的地方 | 改配置为 "pm" 后，项目能正常启动且由 pm 做协调 | 1.5 天 | P0 |
| 0.2 | code_project 配置化 | 删除 `CODE_PROJECT_TASK_TYPES` 硬编码，完全由 `outcome_kind: code_project` 驱动 | 新增一个 task_type 设 outcome_kind=code_project，验证包态逻辑正常 | 0.5 天 | P0 |
| 0.3 | PGD 严格类型配置化 | 在 templates.yaml 增加 `strict_must_include` 字段，删除 `_PGD_STRICT_TYPES` | 给新 task_type 设 strict_must_include=true，验证 must_include 强校验生效 | 0.5 天 | P0 |
| 0.4 | Agent 显示名统一 | 从 agents_registry.json 的 name 字段读取显示名，删除 `_AGENT_DISPLAY_NAMES` | 新增 agent 后，所有 UI 位置显示正确的中文名 | 0.5 天 | P1 |
| 0.5 | 修复 KB API 绕过抽象 | observability_api.py 的 memory CRUD 改走 KnowledgeBackend 接口 | 切换 gbrain 后端后，KB API 行为一致 | 1 天 | P1 |
| 0.6 | 清理旧 project_service 路径 | project_service.py 和 project_group_service.py 从读 task_data.json 改为读 SQLite | 删除所有 task_data.json 后，项目列表和详情页正常显示 | 1 天 | P0 |

**Phase 0 验证标准：**
- 所有 P0 任务完成
- 现有测试全部通过
- 新增 3 个配置化验证测试（协调者、code_project、严格类型）
- 项目列表和详情页完全走 SQLite 新路径

---

### Phase 1：三库独立（高价值，7 天）

> 目标：知识库、偏好库、项目库各自有清晰的边界和独立的接口

| 序号 | 任务 | 内容 | 验证方法 | 工作量 | 优先级 |
|------|------|------|---------|--------|--------|
| 1.1 | 偏好库独立确认 | 清理偏好库对 agent_registry 的依赖，注入式获取 agent 列表 | 偏好库模块可独立 import 且不依赖 hub 层 | 0.5 天 | P1 |
| 1.2 | 知识库存储解耦 | 在 memstack 内定义 MemoryStore Protocol，SQLite 实现内聚到 memstack | KB 后端可独立切换，不依赖 common.store | 2 天 | P1 |
| 1.3 | 统一项目 meta schema | 定义 ProjectMeta Pydantic 模型，规范所有 meta 字段读写 | 各模块通过 ProjectMeta 读写，不再直接操作 JSON dict | 1.5 天 | P1 |
| 1.4 | 封装项目库模块 | 新建 common/project/ 子目录，封装所有项目相关操作 | 项目 CRUD/交付物/可观测性通过统一接口访问 | 2 天 | P1 |
| 1.5 | 打破 harness-memstack 双向依赖 | 存储层独立为 memstore 库，harness 和 memstack 都依赖它 | 依赖方向单向，无循环 import | 1 天 | P1 |

**Phase 1 验证标准：**
- 偏好库可独立运行单元测试
- 知识库可独立切换后端（sqlite → mock）
- 项目库有统一的 ProjectLib 门面类
- 无循环 import
- 所有现有测试通过

---

### Phase 2：结构整理（架构收益大，7 天）

> 目标：代码结构清晰，新人能快速建立心智模型

| 序号 | 任务 | 内容 | 验证方法 | 工作量 | 优先级 |
|------|------|------|---------|--------|--------|
| 2.1 | 拆分 common/ 子目录 | 按 kernel/agent/skill/workflow/store/project/prompt/observability/config 分组 | 所有 import 通过 re-export 兼容，测试通过 | 2 天 | P0 |
| 2.2 | 拆分 server.py 端点 | 37 个端点迁移到 routes/ 下，server.py 只保留初始化 | API 端点行为完全一致（用集成测试验证） | 2 天 | P0 |
| 2.3 | 统一路径常量 | 合并 common/paths.py 和 hub/paths.py 到 backend/paths.py | 全局搜索无重复定义 | 0.5 天 | P1 |
| 2.4 | 重命名 frontend-v2 → frontend | 目录名 + 后端变量同步修改 | 前端正常构建和访问 | 0.5 天 | P1 |
| 2.5 | 整理 Skill 功能结构 | 所有 skill_*.py 移入 common/skill/ 子目录 | Skill 功能统一组织 | 0.5 天 | P1 |
| 2.6 | 整理 MCP 功能结构 | 所有 mcp 相关统一组织 | MCP 功能统一组织 | 0.5 天 | P1 |
| 2.7 | 清理 agentic-workflows | 移入 playbooks/ 或删除 | 确认无代码引用 | 0.5 天 | P2 |
| 2.8 | 统一 API 路由组织 | 所有路由模块平级在 routes/ 下 | 无顶层 *_api.py 文件 | 0.5 天 | P2 |

**Phase 2 验证标准：**
- 所有现有测试通过
- import 路径通过 re-export 保持向后兼容
- 目录结构清晰，新人 30 分钟内能找到对应功能
- server.py 不超过 200 行（不含 lifespan）

---

### Phase 3：质量闭环（产品价值高，10 天）

> 目标：五层质量防御体系完全打通，质量数据可观测、可反馈

| 序号 | 任务 | 内容 | 验证方法 | 工作量 | 优先级 |
|------|------|------|---------|--------|--------|
| 3.1 | Rubric 扩展到更多任务类型 | 为 coding/research/design 等任务类型增加 Rubric 评分维度 | 不同 task_type 有对应的评分维度和红线 | 2 天 | P1 |
| 3.2 | 质量画像页面 | 前端增加 Agent 质量画像页面，展示各维度趋势 | 能看到 Agent 的通过率/自评/评审/重试次数趋势 | 2 天 | P1 |
| 3.3 | 质量反馈驱动任务分配 | team_config 阶段参考质量画像数据选择 Agent | 质量评分高的 Agent 被优先分配对应类型任务 | 2 天 | P1 |
| 3.4 | Skill 评审可观测化 | skill_review 从 daemon 线程改为可追踪的后台任务 | 能在 UI 上看到 skill_review 的状态和结果 | 1.5 天 | P2 |
| 3.5 | 自改进闭环端到端打通 | self_improve_loop 能自动执行完整的评测-补强-再评测循环 | 一个低质量任务触发自改进，3 轮内质量提升 | 2 天 | P2 |
| 3.6 | 交付物元数据表 | 新增 deliverable 表，记录交付物元数据 | 交付物列表从 DB 查询，不扫文件系统 | 0.5 天 | P2 |

**Phase 3 验证标准：**
- 至少 3 种任务类型有 Rubric 评分
- 质量画像页面可访问且数据准确
- team_config 阶段能看到质量评分参考
- 自改进循环可端到端运行（用测试任务验证）

---

### Phase 4：配置 UI 全覆盖（用户价值高，12 天）

> 目标：所有用户配置项都有对应的前端管理页面，用户不需要手动编辑配置文件

**P0 核心配置 UI（5 天）：**

| 序号 | 任务 | 内容 | 验证方法 | 工作量 | 优先级 |
|------|------|------|---------|--------|--------|
| 4.1 | Prompt 模板管理 UI + API | 后端新增 prompt_templates CRUD API；前端新增 `/manage/prompts` 页面，按 kind + task_type 分组编辑 | 在 UI 上修改 prompt 模板，重启后 Agent 使用新模板 | 2 天 | P0 |
| 4.2 | Prompt 注入管理 UI + API | 后端新增 prompt_injections CRUD API；前端与 Prompt 模板合并管理 | 在 UI 上修改注入块，验证注入生效 | 1 天 | P0 |
| 4.3 | Delivery Profiles 管理 UI + API | 后端新增 delivery_profiles CRUD API；前端在交付模板页新增 Profile 子视图 | 创建新 profile 后，workflow 可选择使用 | 1 天 | P0 |
| 4.4 | Agent 注册表编辑 UI + API | 后端新增 agents_registry 写 API；前端 Agent 详情页增加「角色与能力」编辑区 | 修改 Agent 角色能力后，协作上下文同步更新 | 1 天 | P0 |
| 4.5 | task_type_agent_priority 管理 UI + API | 后端新增优先级配置 API；前端任务类型详情页增加「执行优先级」配置 | 修改优先级后，任务分配顺序变化 | 0.5 天 | P0 |

**P1 效率提升 UI（5 天）：**

| 序号 | 任务 | 内容 | 验证方法 | 工作量 | 优先级 |
|------|------|------|---------|--------|--------|
| 4.6 | 知识库模板管理 UI + API | 后端新增 kb_templates API；前端知识库页增加「模板设置」 | 新增 KB 模板后，新建条目使用新模板 | 0.5 天 | P1 |
| 4.7 | task_type_skills 映射管理 UI + API | 后端新增映射 API；前端任务类型详情页增加 Skill 映射配置 | 修改映射后，execute harness 推荐对应 Skill | 0.5 天 | P1 |
| 4.8 | Skill Matrix 审计可视化 | 前端 Skill 页增加「覆盖度审计」面板，展示 task_type × skill 覆盖矩阵 | 能看到哪些任务类型缺少 Skill 覆盖 | 1 天 | P1 |
| 4.9 | 偏好分节管理 UI + API | 后端新增 preference_sections API；前端偏好库页增加分节编辑视图 | 新增分节后，偏好库按新分节组织 | 0.5 天 | P1 |
| 4.10 | Workflow Profiles 管理 UI + API | 后端新增 workflow profile API；前端工作流编辑器增加 Profile 选择/编辑 | 选择不同 profile 后，workflow 行为变化 | 1 天 | P1 |
| 4.11 | 工作区文件编辑扩展 | 前端 Agent 详情页支持编辑 AGENTS.md/TOOLS.md/MEMORY.md/HEARTBEAT.md | 能在 UI 上编辑所有工作区身份文件 | 0.5 天 | P1 |
| 4.12 | agent_task_type_rules 管理 UI + API | 后端新增规则 API；前端任务类型页增加规则编辑器 | 修改推断规则后，自动任务类型匹配变化 | 1 天 | P1 |

**P2 高级功能 UI（2 天）：**

| 序号 | 任务 | 内容 | 验证方法 | 工作量 | 优先级 |
|------|------|------|---------|--------|--------|
| 4.13 | PGD 配置管理 UI | 设置页新增 PGD 子 tab，管理默认模型和角色边界 | 修改 PGD 配置后，PGD 功能行为变化 | 0.5 天 | P2 |
| 4.14 | Skill 组管理 UI | 前端 Skill 页增加「组管理」，支持 vendor 套件批量挂载 | 能创建/编辑 Skill 组并批量挂载到 Agent | 0.5 天 | P2 |
| 4.15 | 配置导入/导出 | 所有配置支持 JSON/YAML 导入导出，方便备份和迁移 | 导出配置后重新导入，配置完全一致 | 1 天 | P2 |

**Phase 4 验证标准：**
- 配置 UI 覆盖率从 75% 提升到 100%（127 项配置全部有 UI）
- 所有 P0 任务完成
- 新增配置管理相关的集成测试
- 用户完成一次完整的团队配置（角色+任务类型+workflow+skill）不需要手动编辑任何配置文件
- 所有现有测试通过

---

## 七、总体工作量与时间线

### 7.1 工作量汇总

| 阶段 | 工作量 | 核心目标 |
|------|--------|---------|
| Phase 0：边界澄清 | 5 天 | 产品能力与用户配置能力界线清晰 |
| Phase 1：三库独立 | 7 天 | 知识库/偏好库/项目库各自独立 |
| Phase 2：结构整理 | 7 天 | 代码结构清晰，可维护性提升 |
| Phase 3：质量闭环 | 10 天 | 五层质量防御体系完全打通 |
| Phase 4：配置 UI 全覆盖 | 12 天 | 所有用户配置项都有前端管理页面 |
| **总计** | **41 天** | |

### 7.2 建议的实施顺序

**第一梯队（必须做，12 天）：**
- Phase 0 全部（5天）+ Phase 2.1/2.2（4天）+ Phase 1.6（清理旧路径，1天）+ Phase 1.3（meta schema，2天）
- 理由：边界澄清 + 结构整理是基础，先做了后续工作才好展开

**第二梯队（应该做，17 天）：**
- Phase 1 剩余部分（5天）+ Phase 2 剩余部分（5天）+ Phase 4 P0 核心配置 UI（5天）+ Phase 4 P1 部分（2天）
- 理由：三库独立 + 配置 UI 是用户能直接感受到的价值，优先补齐

**第三梯队（可以做，12 天）：**
- Phase 3（10天）+ Phase 4 P1 剩余 + P2（2天）
- 理由：质量闭环和体验完善，提升产品价值，但不影响核心架构

### 7.3 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 重构引入回归 | 中 | 高 | 每阶段完成后跑全套测试；保留 re-export 兼容层 |
| 边界重构影响现有功能 | 中 | 中 | 引入配置开关，默认值与旧行为一致 |
| 旧路径清理不彻底 | 中 | 中 | 用 grep 全面扫描引用，逐步 deprecated |
| 测试覆盖不足 | 低 | 中 | 重构前先补关键路径的集成测试 |
| 工作量预估不足 | 中 | 低 | 按 1.5x 预估，预留缓冲 |

---

## 八、验证与验收标准

### 8.1 可验证性原则

每个升级任务都必须满足：
1. **有明确的验收标准**：完成 vs 未完成，不是"差不多"
2. **有自动化测试**：单元测试或集成测试，可重复验证
3. **不破坏现有功能**：所有现有测试通过
4. **向后兼容**：旧的调用方式仍能工作（通过兼容层）

### 8.2 各阶段验收清单

#### Phase 0 验收
- [ ] 协调者角色可通过配置修改，修改后项目正常运行
- [ ] 新增 task_type 设置 outcome_kind=code_project 后，包态逻辑正常
- [ ] 新增 task_type 设置 strict_must_include=true 后，强校验生效
- [ ] 所有 Agent 显示名从 agents_registry.json 读取
- [ ] observability_api 的 memory 操作走 KnowledgeBackend 接口
- [ ] project_service 和 project_group_service 不再读 task_data.json
- [ ] 所有现有测试通过

#### Phase 1 验收
- [ ] 偏好库模块可独立 import（不依赖 hub）
- [ ] 知识库有独立的 MemoryStore Protocol
- [ ] KB 后端可独立切换，不依赖 common.store
- [ ] ProjectMeta Pydantic 模型定义并被所有模块使用
- [ ] 项目库有统一的 ProjectLib 门面类
- [ ] 无循环 import（用 import-linter 或类似工具检查）
- [ ] 所有现有测试通过

#### Phase 2 验收
- [ ] common/ 下有 8+ 个子目录，无子目录外的功能模块
- [ ] server.py 不超过 200 行（不含 lifespan 和静态文件）
- [ ] 只有一个 paths.py 定义路径常量
- [ ] frontend 目录名已改为 frontend/
- [ ] Skill 和 MCP 功能各自有统一的目录组织
- [ ] 所有 API 路由统一在 routes/ 下
- [ ] 所有现有测试通过

#### Phase 3 验收
- [ ] 至少 3 种非产品类任务类型有 Rubric 评分
- [ ] 质量画像页面可访问，展示 Agent 质量趋势
- [ ] team_config 阶段参考质量画像分配任务
- [ ] skill_review 有可观测的状态和结果
- [ ] 自改进循环可端到端运行（有测试验证）
- [ ] deliverable 表存在并被使用
- [ ] 所有现有测试通过

#### Phase 4 验收
- [ ] Prompt 模板可通过 UI 增删改查，修改后生效
- [ ] Prompt 注入块可通过 UI 管理，注入效果正确
- [ ] Delivery Profiles 可通过 UI 创建/编辑/删除
- [ ] Agent 注册表（角色/能力/task_types）可通过 UI 编辑
- [ ] task_type_agent_priority 可通过 UI 配置，分配顺序正确
- [ ] 知识库模板可通过 UI 管理
- [ ] task_type_skills 映射可通过 UI 配置
- [ ] Skill Matrix 覆盖度审计页面可访问
- [ ] 偏好库分节可通过 UI 编辑
- [ ] Workflow Profiles 可通过 UI 选择和编辑
- [ ] Agent 工作区所有身份文件（AGENTS/TOOLS/MEMORY/HEARTBEAT）可通过 UI 编辑
- [ ] agent_task_type_rules 可通过 UI 配置
- [ ] 配置 UI 覆盖率达到 100%（127 项配置全部有 UI 入口）
- [ ] 用户完成完整团队配置流程不需要手动编辑任何配置文件
- [ ] 所有现有测试通过

---

## 九、附录：关键文件索引

| 问题领域 | 关键文件 | 说明 |
|---------|---------|------|
| 协调者硬编码 | `backend/common/decision_pipeline.py` | 最集中的硬编码位置 |
| code_project 硬编码 | `backend/common/project_artifacts.py` | CODE_PROJECT_TASK_TYPES |
| PGD 严格类型 | `backend/common/gate.py` | _PGD_STRICT_TYPES |
| 显示名硬编码 | `backend/common/agent_transport.py` | _AGENT_DISPLAY_NAMES |
| KB 存储耦合 | `backend/memstack/kb/sqlite.py` | 直接依赖 Store |
| 旧路径问题 | `backend/hub/services/project_service.py` | 读 task_data.json |
| common/ 膨胀 | `backend/common/` | 85 个模块平铺 |
| server.py 膨胀 | `backend/hub/api/server.py` | 975 行 37 端点 |
| 双 paths.py | `backend/common/paths.py` + `backend/hub/paths.py` | 重复定义 |
| 自改进闭环 | `backend/execution_harness/self_improve_loop.py` | 框架未完全打通 |
| 质量画像 | `backend/execution_harness/post/quality.py` | 有数据无展示 |
| 双向依赖 | `backend/memstack/facade.py` + `backend/execution_harness/` | 互相调用 |
