# myteam 架构说明

> 版本：2026-06-11 · 分支：`upgrade/continued`  
> **v1 能力计划（执行权威）**：[`docs/V1_CAPABILITY_PLAN.md`](./V1_CAPABILITY_PLAN.md)  
> **框架封板**：[`docs/FRAMEWORK-FREEZE.md`](./FRAMEWORK-FREEZE.md)（L1/L2 已封；增量在 workflow/Skill）  
> REG/E2E 基线：[`docs/PRODUCTION_BASELINE.md`](./PRODUCTION_BASELINE.md)  
> 金路径与 E2E 配方见 [`docs/0608/15-标准协作模式总结.md`](./0608/15-标准协作模式总结.md)。

---

## 1. 两条正交流

| 流 | 入口 | 协作方式 |
|----|------|----------|
| **A. Hub 聊天 / 群聊** | `./run.sh start` → `frontend/` | 人 ↔ 单 Agent，SSE 流式；`chat_service` → `agent_chat` → CLI 适配器 |
| **B. 编排内核** | `run_kernel.py` / Hub「运行项目」 | 目标 → DAG → 多 Agent **由 Process 调度**；Agent **不互读** `.trigger` |

内核与 Hub **共用** `business/tasks/state.db`，但编排**不依赖** Hub 进程。

---

## 2. 三层职责（System / Strategy / Skill）

| 层 | 路径 | 持有 |
|----|------|------|
| **System Kernel** | `backend/common/`、`backend/adapter/`、`hub/api/observability_api.py` | Process、AgentPort、Gate、Store、contracts、看门狗、恢复 |
| **Strategy Registry** | `business/templates/templates.yaml`、`prompt_templates.yaml`、`business/config/agents_registry.json`、`business/workflows/`、`business/rules/` | task_type、prompt 壳、名册、workflow、验收与证据规则 |
| **Skill Pack** | `business/skills/*/SKILL.md`、`workspace-*/AGENTS.md` | 具体执行步骤与角色人设 |

**决策规则**：污染系统状态 → Kernel；改 task_type / 角色 / 验收 → Registry；只影响单次质量 → Skill。  
**框架/业务边界清单**：[`docs/FRAMEWORK_BOUNDARY.md`](./FRAMEWORK_BOUNDARY.md)  
**新增 task_type 必须先写 `templates.yaml`**，不能仅靠 Skill 让 Process 识别。

---

## 3. 编排协作模型（非 Agent 互聊）

```
main: team_config → 选 agent 列表
main: task_plan   → 产出 DAG（agent + task_type + dependencies）
Process: 按 wave 调度 execute / review / triage
```

- **Agent 之间不通过 `.trigger` 对话**；下游通过 execute 提示词里的 **上游摘要**（`task.meta.summary` + 交付物路径）获取依赖信息。  
- **交付物**落在 `business/tasks/project/<id>/deliverables/`（或 code_project 子目录）。  
- **真相**在 SQLite；磁盘文件为传输缓存或人类可读产出。

---

## 4. AgentPort 与 `.trigger` / `.response`

每个 agent workspace：

```
business/workspaces/workspace-<agent_id>/
  .trigger/    # 目录名历史沿用；当前请求文件为 {interaction_id}.request
  .response/   # {interaction_id}.response（submit_result 原子写入）
```

| 文件 | 作用 |
|------|------|
| `{iid}.request` | 内核写入的 InteractionRequest JSON 快照（审计/对账）；**CLI 由内存 prompt 驱动，不轮询此文件** |
| `{iid}.response` | Agent 经 `submit_result.py` 校验契约后写入；AgentPort 轮询采纳 |

旧版 `{project_id}_{task_id}.trigger` 命名已废弃，`workspace_gc` 会清理残留。

交互种类（均走 AgentPort）：`team_config` | `task_plan` | `evaluate` | `execute` | `review` | `triage`。

---

## 5. Execute：Agent 如何知道任务与 Gate

1. **task_type** 来自 DAG；约束单一出处 `templates.yaml` → `registry.get_spec()`。  
2. **本步变量** 写在 task `description`（对象/视角/范围）。  
3. **标准壳** `business/templates/prompt_templates.yaml` → `render_execute_intent()` → worker prompt。  
4. **格式/Gate 摘要** 由 `build_worker_prompt()` 注入（必需章节、验收标准、submit 命令）。  
5. **可选** `business/skills/<task_type>/SKILL.md` 路径提示 Agent 阅读。  
6. **交付物骨架** `deliverable_guarantee.scaffold_markdown_deliverable` 预写 `# 标题` + 空 `## 章节`；**任务意图只进 prompt，不写进交付物文件**。  
7. **Gate** 在 `submit_result` 之后由内核 deterministic 校验；失败项通过 `retry_feedback` 回灌下一轮 prompt。

---

## 6. Agent 名册（权威源）

**模板名册**：`business/templates/business-roster.json`（四条业务线，17 个角色）。

合并到运行态：

```bash
python3 scripts/bootstrap_business_roster.py
```

写入 `business/config/agents_registry.json` 并创建缺失 workspace。

| 说明 | agent id |
|------|----------|
| 协调 / 规划 | `main`、`deputy` |
| 产品 / 架构 / 研发 | `product`、`arch`、`developer`、`frontend` |
| 测试 | `tester`、`qa`、`test_dev` |
| **调研（专职）** | **`research`**（研究员） |
| 数据 / 内容 / 增长 | `analyst`、`content`、`docs`、`seo`、`geo`、`social` |
| 运维 | `ops` |

> **`researcher` 为已废弃的旧 id**。内核 `agent_id_policy` 会在 plan/team_config 将其**自动映射为 `research`**；`auto_create` **拒绝**未在 `agents_registry` / `business-roster` 中的 id。调研任务使用 `task_type=research`，执行者优先 `research`，或由 `product` / `arch` / `developer` 等具备 `research` 能力的角色承担。

`task_type`（如 `research`）与 `agent id`（如 `research`）是不同维度：前者定格式与 Gate，后者定「谁跑 CLI」。

---

## 7. 并行与配置

- DAG 按 **wave** 调度：依赖满足的任务进入同一 wave。  
- **并行**需 `parallel_enabled=true` 且 wave 内多任务；受 `max_parallel` 限制。  
- 全局默认：`config/skill_config.json` → `process_defaults`。  
- Workflow 级：`business/workflows/*.yaml` → `options.parallel_enabled`。  
- **已知**：Hub 后台跑内核时若预构造 `ProcessConfig`，workflow 的 `parallel_enabled` 可能被全局默认覆盖（CLI 直跑 `run_kernel.py` 无此问题）。详见 `docs/0608/15` §7.2。

---

## 8. 模块地图（编排）

```
run_kernel.py
  → Process
      → DecisionPipeline   (team_config / task_plan / evaluate / triage)
      → TaskPipeline       (execute / review + Gate 重试)
      → AgentPort          (.request / .response + 看门狗)
          → agent_transport.build_worker_prompt
          → adapters/opencode | adapters/claude
      → Store              (state.db)
```

---

## 9. 前后端分工与端口化

系统通过 **端口（Port）** 隔离「做什么」与「用什么跑」：

| 层 | 职责 | 端口入口 |
|----|------|----------|
| **System Kernel** | DAG 调度、AgentPort、Gate、Store 真相 | `AgentPort` + 注入 `Transport` / `TokenUsageSink` |
| **Hub** | 聊天 SSE、项目启动、REST 域路由 | `CLIAdapter` registry、`deps.we_store()` |
| **Frontend** | UI 与 HTTP 客户端 | `frontend-v2/src/lib/api/{chat,projects,...}.ts` |

**契约 → 注册/注入 → 实现** 的统一说明、全端口对照表与 codex/cursor stub 状态见 **[`docs/ARCHITECTURE-PORTS.md`](./ARCHITECTURE-PORTS.md)**。

Hub API 按域拆分至 `backend/hub/api/routes/`（channels、projects、chat、workflows、jobs、workspace_events 等）；`server.py` 保留 lifespan、静态资源与尚未拆出的路由。

---

## 10. 相关文档

| 文档 | 内容 |
|------|------|
| [README.md](../README.md) | 安装、启停、冒烟 |
| [CLAUDE.md](../CLAUDE.md) | 开发 invariant、命令 |
| [docs/0608/15-标准协作模式总结.md](./0608/15-标准协作模式总结.md) | 金路径、E2E、反模式 |
| [docs/new/01-整体指导-架构与目标.md](./new/01-整体指导-架构与目标.md) | 需求级架构与序列图 |
| [DESIGN-AGENT-DELIVERY.md](./DESIGN-AGENT-DELIVERY.md) | A/B 双块组合 · 单兵交付 · means |
| [business/workflows/README.md](../business/workflows/README.md) | PGD workflow |
| [docs/framework-decisions.md](./framework-decisions.md) | D1–D19 决策索引 |
