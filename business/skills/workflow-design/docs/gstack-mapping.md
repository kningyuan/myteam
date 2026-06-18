# gstack → myteam 映射方案

> 创建：2026-06-17  
> 参与者：Claude、Auto  
> 状态：**已 supersede 主干** → 见 [`docs/plans/gstack-myteam-integration.md`](../../../../docs/plans/gstack-myteam-integration.md)  
> 本文件保留作快速对照表。

---

## 核心思路

gstack 是**项目级工具集**（通过 `/xxx` 命令触发），myteam 是**agent 级能力集**（通过 workflow YAML 调度）。

**分工（2026-06 共识）**

| 概念 | 职责 |
|------|------|
| `business/rules/ethos.md` | 哲学（全员默认 rules，非 skill） |
| `business/skills/*/SKILL.md` | 单 Agent 如何完成某类任务；可互相引用（如 qa → browse） |
| `task_type` | 仅配合 workflow 步骤；内核调度 + Gate |
| `business/workflows/*.yaml` | 多步 DAG / loop（对应 gstack 命令链） |

**已建 workflow 样板**（task_type 暂用现有注册表，后续再拆专用工种）：

`计划评审-四轮`、`发版-round`、`代码评审-round`、`质量验收-round`、`问题调查-round`、`回顾-round`、`规格化-round`、`战略对齐-round`、`设计评审-round`、`架构评审-round`

同一套方法论/流程，只是触发方式不同：

| gstack | myteam 对应 | 说明 |
|--------|------------|------|
| `/ship` | `main` + `code-deployment` task_type | 版本 bump + CHANGELOG + PR |
| `/review` | `main` + `section-review` task_type | PR 审查 |
| `/qa` | `qa` + `code-testing` task_type | 测试 + 修 bug |
| `/plan-eng-review` | `arch` + `architecture-review` task_type | 架构审查 |
| `/plan-ceo-review` | `main` + `strategy` task_type | 战略审查 |
| `/design-review` | `frontend` + `code-review` task_type | 视觉审查 |
| `/office-hours` | `main` + `strategy` task_type | 战略对齐 |
| `/spec` | `main` + `requirements` task_type | 需求规格化 |
| `/retro` | `main` + `acceptance-report` task_type | 回顾总结 |
| `/investigate` | `research` + `research` task_type | 问题诊断 |
| `/design-consultation` | `product` + `product-planning` task_type | 设计系统咨询 |
| `/document-generate` | `docs` + `content` task_type | 文档生成 |
| `/canary` | `ops` + `code-deployment` task_type | 部署后监控 |
| `/health` | `qa` + `code-review` task_type | 代码健康检查 |
| `/setup-deploy` | `main` + `code-deployment` task_type | 部署配置 |

---

## 映射原则

1. **方法论不变** — gstack 的 skill 内容是"做什么"，myteam 的 skill 是"谁做 + 怎么做"
2. **触发方式不同** — gstack 是人触发，myteam 是内核调度
3. **能力挂载** — gstack 的 preamble-tier 对应 myteam 的 agent workspace 注入
4. **workflow 替代命令链** — gstack 的 `/autoplan`（CEO→Design→Eng→DX）对应 myteam 的 workflow YAML（多 step DAG）

---

## 需要新增的 myteam 概念

| 现有 | 缺失 | 建议 |
|------|------|------|
| `quality-review` skill | 无对应 | 已有，覆盖 L1-L4 审查 |
| `workflow-design` skill | 无对应 | 已有，覆盖 workflow 编排 |
| — | `ship` workflow | 新增：VERSION bump + CHANGELOG + PR |
| — | `retro` workflow | 新增：回顾总结 + learnings 归档 |
| — | `spec` workflow | 新增：模糊意图 → 可执行规格 |
| — | `health` workflow | 新增：代码健康检查 |
| — | `canary` workflow | 新增：部署后监控 |
| — | `investigate` workflow | 新增：问题诊断 |
| — | `document-generate` workflow | 新增：文档生成 |

---

## 哲学层映射

gstack ETHOS → `business/rules/ethos.md`（**全员默认 rules**，interactive / discussion / workflow_execute 均加载；**不是 skill**）：

| gstack ETHOS | myteam 对应 |
|-------------|------------|
| Boil the Ocean | ethos.md §1 |
| Search Before Building | ethos.md §2；各 methodology skill 的勘察步骤 |
| User Sovereignty | ethos.md §3；coordination-methodology 决策纪律 |

browse → 独立 skill `business/skills/browse/`；qa / frontend 等按需在管理页挂载。

---

## 待讨论

- [ ] 哪些 gstack skills 是"工具型"（browse、iOS）不应映射？
- [ ] gbrain 是否值得引入？
- [ ] 映射后，myteam 的 catalog.yaml 需要更新哪些 task_type → skill 路由？
