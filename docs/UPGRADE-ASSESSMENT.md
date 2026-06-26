# myteam 升级评估报告

> 生成日期：2026-06-26
> 评估范围：全量代码库深度分析（8个维度）

---

## 一、执行摘要

### 1.1 核心结论

myteam 的架构设计整体优秀——三层架构（System Kernel / Strategy Registry / Skill Pack）方向正确，适配器隔离、Interaction 契约、Gate 单源原则等核心设计扎实。但在以下方面需要升级：

1. **边界清晰度**：系统能力与用户配置能力的边界存在 10+ 处硬编码泄露（最严重的是 `main` 协调者角色渗透）
2. **模块独立性**：知识库、偏好库、项目库在架构上已具备独立雏形，但存储层和部分调用路径存在耦合
3. **代码组织结构**：`backend/common/`（85个模块平铺）和 `hub/api/server.py`（975行/37端点）过于臃肿，缺乏子目录分组
4. **历史遗留**：存在 `agentic-workflows/`、`task_data.json` 等过渡/遗留产物

### 1.2 升级原则

- **不破坏核心流程**：聊天、群组、编排内核的主流程保持不变
- **机制留内核，策略归配置**：能配置化的绝不硬编码
- **渐进式重构**：分阶段实施，每阶段可独立验证
- **向后兼容**：所有重构提供兼容层，避免破坏性变更

---

## 二、系统能力 vs 用户配置能力边界

### 2.1 现状总览

| 层级 | 位置 | 内容 | 边界清晰度 |
|------|------|------|-----------|
| **系统内核** | `backend/common/` + `backend/adapter/` | Process状态机、AgentPort、Gate、Store、contracts、适配器 | 基本清晰，但有10+处业务策略硬编码泄露 |
| **策略注册层** | `business/templates/` + `business/config/` + `business/workflows/` | task_type定义、Agent角色、工作流、规则配置 | 配置内容完整，但UI管理覆盖不足（仅40%有管理界面） |
| **技能包层** | `business/skills/` | 各领域方法论、执行指南 | 边界清晰，catalog.yaml索引机制良好 |

### 2.2 边界模糊点（按严重度排序）

#### 🔴 P0 - 高优先级

**1. 协调者角色硬编码为 `"main"`**
- **位置**：`backend/common/decision_pipeline.py`、`backend/common/process.py`、`backend/common/workflow_loader.py` 等 8+ 处
- **问题**：用户无法自定义协调者角色ID，新增协调型角色受限制
- **方案**：引入 `coordinator_agent_id` 配置项，默认 `"main"`，从 `system_config.json` 或 `agents_registry.json` 读取

**2. 代码项目类型硬编码**
- **位置**：`backend/common/project_artifacts.py` 的 `CODE_PROJECT_TASK_TYPES`
- **问题**：只有 `code-deliverable/code-writing/code-testing` 被当作多文件项目，用户新增 code 类 task_type 不走包态逻辑
- **方案**：完全由 `templates.yaml` 中的 `outcome_kind: code_project` 驱动

#### 🟡 P1 - 中优先级

**3. PGD 严格校验类型硬编码**
- `gate.py` 中 `_PGD_STRICT_TYPES = frozenset({"decision-record", "acceptance-report"})`
- 方案：在 `templates.yaml` 增加 `strict_must_include: true` 字段

**4. Agent 显示名硬编码**
- `agent_transport.py` 中 `_AGENT_DISPLAY_NAMES` 只覆盖5个角色
- 方案：统一从 `agents_registry.json` 的 `name` 字段读取

**5. 工作流推导模板硬编码**
- `workflow_suggest.py` 中 `_github_parallel_tasks()`、`_smoke_tasks()` 等是业务场景
- 方案：移到 `business/templates/workflow-suggestions/` 下配置化

**6. 身份文件模板硬编码**
- `agent_bootstrap.py` 中 `IDENTITY_TEMPLATES` 含中文文案
- 方案：移到 `business/templates/identity-templates/`

**7. 规则 profile 映射硬编码**
- `rules_merge.py` 中 profile → 文件名的映射
- 方案：配置化 profile → files 映射，支持自定义 profile

#### 🟢 P2 - 低优先级

**8. 占位符标记硬编码**（`registry.py` 的 `_PLACEHOLDER_MARKERS`）
**9. 反爬拦截标记硬编码**（`gate.py` 的 `_BLOCKED_MARKERS`）
**10. 代码扩展名硬编码**（`gate.py` / `project_artifacts.py` 的 `_CODE_EXTS`）
**11. 废弃 agent 别名硬编码**（`agent_id_policy.py` 的 `DEPRECATED_AGENT_ALIASES`）

### 2.3 UI 管理覆盖缺口

以下配置有文件但**无对应 UI 管理页**：
- `delivery_profiles.yaml` — 交付套餐
- `prompt_injections.yaml` — Prompt 注入块
- `prompt_templates.yaml` — Prompt 模板
- `task_type_skills.yaml` — task_type → skill 映射
- `task_type_agent_priority.json` — 任务分配优先级
- `agent_task_type_rules.json` — 关键词推导规则

---

## 三、知识库、偏好库、项目库独立性评估

### 3.1 知识库（KB）

**现状**：
- 架构：`backend/memstack/kb/` 有干净的 `KnowledgeBackend` Protocol 和注册表模式
- 存储：与 L1 共用 `store.memory` 表，通过 `project_id` 区分
- 调用：`observability_api.py` 直接调 `store.memory_*`（绕过抽象层）
- 结构化模板：`business/config/kb_templates.yaml`

**独立可行性：高**
- 解耦路径：在 memstack 内定义独立的 `MemoryStore` Protocol，SQLite 实现内聚到 memstack 内部
- 可独立为 Python 库，供其他项目复用
- 需修复：`observability_api.py` 应走 `KnowledgeBackend` 接口而非直接操作 Store

### 3.2 偏好库

**现状**：
- 架构：`backend/memstack/preferences/` 有 `PreferenceBackend` Protocol，多后端实现（static/mem0/user_store）
- 存储：`config/USER.md` + 各 agent workspace 的 USER.md
- API：已有 `preferences_api.py` REST 接口
- 分节配置：`business/config/preference_sections.yaml`

**独立可行性：极高**
- 接口最简单，数据量最小
- 已有完整的 CRUD API
- 唯一耦合：同步到各 agent workspace 的逻辑依赖 `agent_registry`

### 3.3 项目库

**现状**：
- 核心数据已集中在 SQLite（project/task/interaction/run_event 表）
- 但存在**双轨数据**：新内核用 SQLite，旧路径用 `task_data.json`
- 交付物完全依赖文件系统路径约定，无元数据索引
- 项目 meta 是无 schema 的 JSON 字段，各模块随意写入

**独立可行性：中高**
- 最大障碍：旧版 `task_data.json` 路径未清理（`project_service.py`、`project_group_service.py` 仍在读取）
- 第二障碍：交付物管理与文件系统强耦合，无统一元数据表

**建议的独立方案（轻量级）**：
```
project_lib/                     # 新增独立模块
├── store/                       # 项目表 CRUD（从 Store 中剥离）
├── artifacts/                   # 交付物管理（从 project_artifacts.py 迁移）
├── admin/                       # 项目删除/归档
├── observability/               # 只读查询（从 observability.py 迁移）
└── api/                         # 统一项目 API（替代旧版 project_service）
```

**留在内核侧**：
- `process.py` — 项目执行引擎
- `project_runtime.py` — 进程内调度
- `project_cancel.py` — 取消信号
- `project_hooks.py` — 回调接口

### 3.4 memstack 与 execution_harness 的双向依赖问题

```
memstack.facade ──委托──▶ execution_harness.inject_for_execute
    ▲                                    │
    └────── 复用 KB/L1/偏好 adapter ──────┘
```

**问题**：两者职责边界模糊。harness 做注入编排，memstack 做存储+部分编排，形成双向依赖。

**建议**：
- 方案A：把 execute 注入逻辑完全移入 memstack，harness 只调用 memstack
- 方案B：把 memstack 的存储 adapter 完全独立成库（`memstore`），harness 和 memstack 都依赖这个库

---

## 四、代码结构调整建议

### 4.1 目录结构重构（P0 - 最高优先级）

#### 问题1：`backend/common/` 85个模块平铺

**当前问题**：85个 `.py` 文件平铺，没有子目录分组，新人无法快速建立心智模型。

**重构方案**：

```
backend/common/
├── kernel/                      # 内核核心（状态机+门禁+契约）
│   ├── process.py
│   ├── process_types.py
│   ├── gate.py
│   ├── contracts.py
│   ├── dag_dispatch.py
│   ├── task_pipeline.py
│   ├── decision_pipeline.py
│   ├── plan_expansion.py
│   ├── plan_gate.py
│   ├── plan_splice.py
│   └── deliverable_guarantee.py
├── agent/                       # Agent 交互层
│   ├── agent_port.py
│   ├── agent_transport.py
│   ├── agent_registry.py
│   ├── agent_model.py
│   ├── agent_memory.py
│   ├── agent_skills.py
│   ├── agent_mcp.py
│   ├── agent_bootstrap.py
│   ├── agent_id_policy.py
│   ├── agent_task_type_suggest.py
│   ├── agent_execution.py
│   ├── submit_result.py
│   └── workspace_gc.py
├── skill/                       # Skill 管理
│   ├── skill_catalog.py
│   ├── skill_install.py
│   ├── skill_link.py
│   ├── skill_extract.py
│   ├── skill_groups.py
│   ├── skill_categories.py
│   ├── skill_settings.py
│   ├── skill_display_names.py
│   ├── adapter_skill_registry.py
│   └── agent_skills.py          # （从 agent/ 移入）
├── workflow/                    # Workflow 管理
│   ├── workflow_loader.py
│   ├── workflow_validate.py
│   ├── workflow_bootstrap.py
│   ├── workflow_collaboration.py
│   ├── workflow_capability_bind.py
│   └── workflow_suggest.py
├── loop/                        # 循环/讨论/圆桌
│   ├── loop_runtime.py
│   ├── loop_discussion_runtime.py
│   ├── loop_discussion_dispatch.py
│   ├── roundtable_runtime.py
│   └── roundtable_context.py
├── store/                       # 存储层
│   ├── store.py
│   ├── store_sqlite.py
│   ├── store_backend.py
│   ├── task_data_store.py
│   ├── task_type_store.py
│   ├── group_message_store.py
│   └── delivery_template_store.py
├── project/                     # 项目管理
│   ├── project_runtime.py
│   ├── project_admin.py
│   ├── project_artifacts.py
│   ├── project_cancel.py
│   ├── project_hooks.py
│   ├── kernel_project_hooks.py
│   └── project_service.py       # （从 hub/services 移入并清理旧路径）
├── prompt/                      # Prompt 组装
│   ├── prompt_composer.py
│   ├── prompt_templates.py
│   ├── prompt_injections.py
│   └── context_assembler.py
├── observability/               # 可观测性
│   ├── observability.py
│   ├── token_usage.py
│   ├── audit_log.py
│   ├── ops_log.py
│   ├── thinking_trace.py
│   └── hub_operation_meta.py
├── config/                      # 配置读取
│   ├── kernel_config.py
│   ├── delivery_profiles.py
│   ├── shared_rules.py
│   ├── rules_merge.py
│   ├── registry.py              # FormatSpec 注册表
│   └── task_type_suggest.py
└── paths.py                     # 路径常量
```

#### 问题2：`hub/api/server.py` 975行 / 37+端点

**当前问题**：已有 `routes/` 子目录，但 37 个端点仍留在 `server.py` 中。

**重构方案**：

```
backend/hub/api/
├── server.py                    # 仅保留 app 创建 + 中间件 + lifespan + 静态托管
├── deps.py
├── errors.py
└── routes/                      # 所有路由统一在这里
    ├── agents.py                # + 移入 server.py 中的 agents/* 端点
    ├── chat.py
    ├── groups.py
    ├── projects.py              # + 移入 server.py 中的 projects/* 端点
    ├── workflows.py
    ├── task_types.py            # 新增（从 server.py 移入）
    ├── delivery_templates.py    # 新增（从 server.py 移入）
    ├── observability.py         # 从顶层 observability_api.py 移入
    ├── skills.py                # 从顶层 skills_api.py 移入
    ├── mcp.py                   # 从顶层 mcp_api.py 移入
    ├── preferences.py           # 从顶层 preferences_api.py 移入
    ├── rules.py                 # 从顶层 rules_api.py 移入
    ├── config.py
    └── single_execute.py
```

**原则**：所有路由模块平级组织在 `routes/` 下，消除"顶层API文件"和"routes子目录"并存的混乱。

### 4.2 目录命名调整

| 当前 | 建议 | 优先级 | 理由 |
|------|------|--------|------|
| `backend/adapter/` + `backend/adapters/` | 合并为 `backend/adapters/`，下设 `base/` | P1 | 两个目录只差一个s，极易混淆 |
| `frontend-v2/` | `frontend/` | P1 | ~~已完成~~ v1已完全移除，保留v2无意义 |
| `backend/base/` | 移入 `backend/hub/domain/` | P1 | base含义不清，实际是Hub业务逻辑层 |
| `business/agentic-workflows/` | 移入 `business/playbooks/workflow-designs/` | P1 | 未接入系统的设计态产物，不应与运行态workflows并列 |
| `business/means/` | 并入 `business/skills/` 或改 `business/tools/` | P2 | means命名不直观，且几乎未被使用 |
| `business/agent-catalog/` | 移入 `docs/` 或删除 | P2 | 只有1个示例文件，未接入系统 |

### 4.3 文件位置调整

#### P1 - 重要

**1. 统一路径常量**
- 问题：`common/paths.py` 和 `hub/paths.py` 大量重复定义
- 方案：统一到 `backend/paths.py`，两处做 re-export 兼容

**2. 整理 `backend/store/` 目录**
- 问题：3个文件分属不同关注点（system_config、skill_config、sessions），且与 `common/store.py` 重名
- 方案：
  - `system_config.py` + `skill_config.py` → `backend/config/`
  - `sessions.py` → `backend/hub/services/`

**3. `run_kernel.py` 移出 common/**
- 问题：CLI 入口脚本与 80+ 库模块混在一起
- 方案：移到 `backend/cli/run_kernel.py`

**4. 两个 `agent_registry` 重命名**
- 问题：`common/agent_registry.py`（只读）和 `hub/services/agent_registry.py`（可写管理）同名
- 方案：hub 层改名为 `agent_manager_service.py`

#### P2 - 一般

**5. 清理遗留兼容文件**
- `backend/base/server.py` — 空壳转发
- `backend/base/system_config.py` — 兼容层
- `common/paths.py` 中的遗留别名（TEAM_OK_DIR、SKILLS_DIR 等）

**6. 统一 `delivery` / `deliverable` 命名**
- 问题：`delivery_templates.py` vs `deliverable_guarantee.py`
- 建议：统一为 `deliverable_*`

### 4.4 功能组织调整

#### P1 - Skill 功能整合

当前 Skill 功能分散在 15+ 个文件、5+ 个目录：

```
整合方案：
common/skill/                    # 所有 skill_*.py 移入
hub/services/skill_service.py    # 从 agent_registry.py 中抽出 skill 相关函数
adapters/*/skill_sync.py         # 保持不变（CLI 适配层）
business/skills/                 # 保持不变（Skill 内容）
```

#### P1 - MCP 功能整合

同理，MCP 功能也分散在 3 层，应统一组织方式。

#### P1 - 配置管理层统一

配置文件散落在 5+ 个目录，配置读取代码散落在 10+ 个模块中。建议：

```
backend/config/                  # 统一配置读取层
├── system_config.py             # 从 store/ 移入
├── skill_config.py              # 从 store/ 移入
├── business_config.py           # business/config/ 下各文件的统一读取入口
└── templates_config.py          # business/templates/ 下各文件的统一读取入口
```

---

## 五、升级路线图

### Phase 1：边界澄清（低风险，高价值）—— 约 5 天

| 任务 | 内容 | 验证方式 |
|------|------|---------|
| 1.1 协调者角色配置化 | 引入 `coordinator_agent_id` 配置，默认 "main" | 改配置后验证项目能正常启动 |
| 1.2 code_project 驱动方式 | 用 `outcome_kind: code_project` 替代硬编码列表 | 新增 code 类 task_type 验证包态逻辑 |
| 1.3 Agent 显示名统一 | 从 agents_registry.json 读取显示名 | 检查所有显示位置是否正确 |
| 1.4 PGD 严格类型配置化 | 增加 `strict_must_include` 字段 | 验证 decision-record/acceptance-report 行为不变 |
| 1.5 修复 KB 调用绕过抽象 | observability_api.py 走 KnowledgeBackend 接口 | 切换 gbrain 后端验证 API 正常 |

### Phase 2：结构整理（中风险，架构收益大）—— 约 7 天

| 任务 | 内容 | 验证方式 |
|------|------|---------|
| 2.1 拆分 common/ 子目录 | 按 kernel/agent/skill/workflow/... 分组 | 所有测试通过，import 路径兼容 |
| 2.2 拆分 server.py 端点 | 37个端点迁移到 routes/ 下 | 所有 API 端点行为不变 |
| 2.3 统一路径常量 | 合并 common/paths.py 和 hub/paths.py | 全局搜索无重复定义 |
| 2.4 重命名 frontend-v2 → frontend | 目录名 + 后端变量同步 | ~~已完成~~ 前端正常构建访问 |
| 2.5 清理 agentic-workflows | 移入 playbooks/ 或删除 | 确认无代码引用 |

### Phase 3：库独立（中高风险，长期收益大）—— 约 10 天

| 任务 | 内容 | 验证方式 |
|------|------|---------|
| 3.1 偏好库独立 | 提取为独立的 preferences 服务/库 | CRUD API 正常，同步机制正常 |
| 3.2 知识库独立存储 | memstack 内部定义 MemoryStore Protocol | KB 后端可独立切换 |
| 3.3 项目库轻独立 | 封装 project_lib 模块，清理 task_data.json | 所有项目访问走统一接口 |
| 3.4 打破 harness-memstack 双向依赖 | 存储层独立为 memstore 库 | 依赖方向单向 |

### Phase 4：体验完善（低风险，用户价值）—— 约 5 天

| 任务 | 内容 |
|------|------|
| 4.1 Prompt 配置 UI | 增加 prompt_templates / prompt_injections 的可视化编辑 |
| 4.2 交付套餐管理 UI | delivery_profiles 的管理界面 |
| 4.3 规则 profile 配置化 | 支持用户自定义规则 profile |
| 4.4 工作流推导模板配置化 | 从代码移到配置文件 |

---

## 六、关键文件索引

| 类别 | 文件路径 |
|------|---------|
| 内核核心 | `backend/common/process.py`、`backend/common/agent_port.py`、`backend/common/gate.py`、`backend/common/contracts.py` |
| 存储层 | `backend/common/store.py`、`backend/common/store_sqlite.py` |
| 适配器层 | `backend/adapter/protocol.py`、`backend/adapter/events.py` |
| 任务类型定义 | `business/templates/templates.yaml` |
| 知识库 | `backend/memstack/kb/`、`business/config/kb_templates.yaml` |
| 偏好库 | `backend/memstack/preferences/`、`business/config/preference_sections.yaml` |
| 项目管理 | `backend/common/project_admin.py`、`backend/common/project_artifacts.py` |
| 工作流 | `backend/common/workflow_loader.py`、`business/workflows/` |
| Skill 系统 | `backend/common/skill_catalog.py`、`business/skills/catalog.yaml` |
| Hub API | `backend/hub/api/server.py`（975行）、`backend/hub/api/routes/` |
| 双轨数据问题 | `backend/hub/services/project_service.py`（读 task_data.json） |

---

## 七、总结

myteam 的核心架构设计优秀，升级的重点不是"推倒重来"而是"梳理边界 + 整理结构 + 清理债务"：

1. **边界澄清**是最有价值的工作——把硬编码的业务策略移到配置层，让系统内核真正成为"机制"而非"策略"
2. **三库独立**有坚实基础，但应循序渐进：偏好库 → 知识库 → 项目库，每个都先做接口抽象再物理分离
3. **代码结构**的最大痛点是 `common/` 和 `server.py` 的膨胀，拆分子目录后可大幅降低新人上手成本
4. **所有调整都应保持向后兼容**，通过 re-export、别名、兼容层确保不破坏现有功能
