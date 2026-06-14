# Framework vs Business 边界清单

> 版本：2026-06-11  
> 原则：**Kernel 只提供机制；Strategy/Skill 持有领域知识与业务协议。**

---

## 1. 三层归属（权威）

| 层 | 路径 | Kernel 应实现 | Business 应持有 |
|----|------|---------------|-----------------|
| **System Kernel** | `backend/common/`、`backend/hub/`、`backend/adapters/` | Process、DAG、loop 引擎、Gate、Store、AgentPort、契约、恢复、看门狗、**通用 hook 调度** | — |
| **Strategy Registry** | `business/templates/`、`business/config/`、`business/workflows/`、`business/delivery_templates/` | 加载器、校验器 | task_type、prompt 壳、workflow、交付模板、名册、能力绑定规则 |
| **Skill Pack** | `business/skills/`、`business/inputs/`、`business/hooks/` | 注入路径 | 执行步骤、源材料、**领域 loop 讨论协议** |

**决策规则**：污染全局状态 / 跨项目机制 → Kernel；改验收 / 角色 / 流程图 → Registry；只影响单次质量 → Skill。

---

## 2. Kernel 必须实现（框架能力）

| 能力 | 模块 | 说明 |
|------|------|------|
| 项目生命周期 | `process.py`, `run_kernel.py` | 启动、resume、DAG 调度、loop 占位 |
| Loop 引擎 | `loop_runtime.py` | `until` 判定、轮次实例化、PATCH 基线 |
| Gate | `gate.py`, `registry.py` | 确定性结构/文件校验（读 Registry spec） |
| 契约 | `submit_result.py`, `contracts.py` | Pydantic 校验，拒绝非法响应 |
| 状态 | `store.py` | SQLite 真相库 |
| Agent 传输 | `agent_port.py`, `agent_transport.py` | CLI 子进程、重试、看门狗 |
| 可观测 | `observability.py` | 只读 API 形状 |
| Hook 调度 | `loop_discussion_dispatch.py`, `business_hook_loader.py` | 读 workflow options → 加载 business hook |
| Loop 讨论运行时 | `loop_discussion_runtime.py` | 读交付物、发群消息、存 artifact（**无领域 agent 名/中文评审节名**） |

---

## 3. Business 必须持有（领域内容）

| 内容 | 路径 | 示例 |
|------|------|------|
| Workflow 定义 | `business/workflows/*.yaml` | 产品规划方案、讨论链路测试 |
| 交付模板 | `business/delivery_templates/*.yaml` | `tds-ch3-product-planning` |
| Task type 基线 | `business/templates/templates.yaml` | **通用** `product-planning` 节结构 |
| Prompt 壳 | `business/templates/prompt_templates.yaml` | execute/review 模板 |
| Agent 名册 | `business/config/agents_registry.json` | main/product/… |
| 能力绑定优先级 | `business/config/task_type_agent_priority.json` | publish-post → social_* |
| Agent→task_type 推导规则 | `business/config/agent_task_type_rules.json` | 知乎/小红书关键词 |
| PGD 角色边界 | `business/config/pgd_role_boundaries.json` | 各 agent 职责 Markdown |
| PGD 默认模型 | `business/config/pgd_default_models.json` | workflow bootstrap 用 |
| Loop 讨论 profile | `business/workflows/profiles/*.yaml` | work-review-alignment |
| Loop 讨论 hook | `business/hooks/*.py` | Work–Review 对齐 prompts |
| Skill | `business/skills/*/SKILL.md` | 竞品名、drawio、源文件路径 |
| 源材料 | `business/inputs/` | TDS 第一/二/三章 |

---

## 4. 已迁移项（2026-06-11）

| 原位置（Kernel） | 新位置（Business） | 状态 |
|------------------|-------------------|------|
| `project_group_discussion.py` 全文 | `loop_discussion_runtime.py` + `business/hooks/work_review_alignment.py` | ✅ 拆分 |
| `WORK_AGENT=product`, `REVIEW_AGENT=main` 硬编码 | `profiles/work-review-alignment.yaml` | ✅ |
| 中文评审节名硬编码 | profile `review_sections` | ✅ |
| `workflow_capability_bind.TASK_TYPE_AGENT_PRIORITY` | `config/task_type_agent_priority.json` | ✅ |
| `agent_task_type_suggest._AGENT_RULES` | `config/agent_task_type_rules.json` | ✅ |
| `workflow_bootstrap._ROLE_BOUNDARIES` | `config/pgd_role_boundaries.json` | ✅ |
| `workflow_bootstrap._DEFAULT_BACKEND` | `config/pgd_default_models.json` | ✅ |
| `templates.yaml` TDS 第三章节 | 仅 `delivery_templates/tds-ch3-product-planning.yaml` | ✅ 泛化 base |

---

## 5. Kernel 禁止出现

- 具体产品/客户名（可信数据空间、浪潮、蚂蚁密算…）
- 具体章节号（第三章、H1 第三章…）在 **base task_type**
- 具体 social agent id（`social_zhihu`）在 Python 常量 — 应在 JSON registry
- 领域讨论 prompt 全文
- 「product 必须 / main 必须」类 PGD 业务协议

---

## 6. 扩展新业务的标准路径

1. **新交付形态** → `delivery_templates/<id>.yaml` + goal 里 `template_id`
2. **新协作流程** → `workflows/<id>.yaml`（loops/tasks/options）
3. **新 FAIL 对齐协议** → `workflows/profiles/<id>.yaml` + `business/hooks/<id>.py`，workflow 设 `loop_discussion_profile`
4. **新 Agent 能力** → `agents_registry.json` + `agents_config.json`
5. **新 task_type** → 先写 `templates.yaml`，再写 Skill

**不要**改 `process.py` / `loop_runtime.py` 除非新增 **generic** 原语（如新的 `until` 类型）。

---

## 7. 参考对照（工业框架）

| 工业做法 | myteam 对应 |
|----------|-------------|
| LangGraph StateGraph | `Process` + workflow YAML |
| Checkpointer | `Store` + resume |
| interrupt_before (HITL) | Gate fail → loop / hook |
| 业务节点 | workflow body tasks + hooks |
| 领域 prompt | Skill + delivery_template |

---

## 8. Owner 决策（v1 封板，2026-06-11）

来源：Agent 圆桌（product / arch / frontend / geo / main）+ Owner 拍板。  
完整记录：`business/tasks/project/roundtable-v1-stable/deliverables/roundtable_transcript.md`

### 8.1 arch 评审介入 — **按任务/workflow 配置，不一刀切**

| 场景 | arch 是否介入 | 典型 task_type |
|------|---------------|----------------|
| 产品方案 / PRD | 建议有 **方案 Gate** | `architecture-review` 或 `section-review` |
| 系统研发 / 改代码 | 建议有 **实现 Gate** | `architecture-review` / `code-review` |
| 纯内容 / 媒体运营 | 不需要 | — |
| 小改动 / bugfix | 可跳过方案 Gate | 仅 qa 或 code-review |
| 大版本 / 新模块 | 方案 Gate + 实现 Gate | workflow 里显式两步 |

**规则：** 不在 Kernel 写死次数；在 **workflow YAML** 里按任务链决定是否插入 arch 节点。

### 8.2 SEO vs GEO — **发布前 GEO 优先**

| 阶段 | 规则 |
|------|------|
| **发布前** | 内容验收以 **GEO 可引用性** 优先（结构、实体、FAQ；避免关键词堆砌） |
| **发布后存量** | SEO 与 GEO **各跑各的 workflow**（排名/流量 vs 引用率/审计） |
| **冲突协调** | **每月一次** content + seo + geo 对齐会，会上拍板，不写进 Kernel |

### 8.3 Mac App 用户配置 — **v1 最小安全边界（A/B/C）**

| 代号 | 含义 | v1 要求 |
|------|------|---------|
| **A. 保存前校验** | Hub 在写入 workflow/agent/skill 前校验合法性（task_type 能力、DAG、YAML schema） | ✅ 必须 |
| **B. 不可跳过 Gate** | 运行中用户不能绕过 Gate / 强制 completed | ✅ 必须 |
| **C. 只改 Strategy 层** | 配置仅触及 `business/config`、`workflows/`、`skills/` 等；不碰 Kernel 代码与 Store schema | ✅ 必须 |
| **完整 sandbox / 多用户权限** | 目录隔离、角色、插件签名 | ❌ v2 再做 |

### 8.4 四条业务工作流优先级（圆桌共识）

| 优先级 | 工作流 | 落地方式 |
|--------|--------|----------|
| **P0** | 完整产品研发 | 新 workflow YAML + 现有 PGD task_type |
| **P1** | 媒体持续运营（知乎/小红书） | 新 workflow + zhihu/publish-post skill |
| **P2** | 产品经理 Skill 包 | 组合 product-planning / wps-deck / deck-build |
| **P3** | GEO 持续优化 | content → geo-audit → geo-plan 闭环 |

### 8.5 Kernel v1 冻结项（90 天内不大改）

Process + Gate + loop、`delivery_template` 契约、`submit_result`、AgentPort、Store 五表 schema、461 tests 回归基线。  
**不做：** 分布式调度、Kernel DSL、拖拽编排器、完整 sandbox、GEO 自动采数 API。

---

## 9. 扩展阅读

- **v1 能力达成计划（执行权威）**：[`V1_CAPABILITY_PLAN.md`](./V1_CAPABILITY_PLAN.md)
- REG/E2E 生产基线：[`PRODUCTION_BASELINE.md`](./PRODUCTION_BASELINE.md)
- 架构总览：[`ARCHITECTURE.md`](./ARCHITECTURE.md)
- 框架封板：[`FRAMEWORK-FREEZE.md`](./FRAMEWORK-FREEZE.md)
- 业务 workflow 摘要：[`V1_ROADMAP.md`](./V1_ROADMAP.md)
