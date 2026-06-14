# 方法论 Skill 注册表

myteam 将 **任务 skill**（`business/skills/<task_type>/`）与 **方法论 skill**（`<role>-methodology`）分离：

| 层级 | 路径 | 注入方式 |
|------|------|----------|
| 任务 skill | `business/skills/<task_type>/SKILL.md` | 内核 `agent_transport` 自动注入 |
| 方法论 skill | `business/skills/<methodology>/SKILL.md` | `common/skill_methodology.py` 链式注入 |
| Cursor 发现 | `.cursor/skills/<methodology>/SKILL.md` | Cursor Agent 直接读取 |

内核 execute 提示词顺序：**任务指引 → 方法论（0..n）→ 交付模板 → Gate 章节**。

---

## 角色 ↔ 方法论 ↔ task_type

| 角色 (agent_id) | 方法论 skill | 主要 task_type |
|-----------------|--------------|----------------|
| 产品专家 `product` | `product-methodology` | requirements, strategy, product-planning, acceptance-report, section-* |
| 架构师 `arch` | `system-architecture-methodology` | system-design, architecture-review, arch-research |
| 前端架构/研发 `frontend` | `frontend-architecture-methodology` + `system-architecture-methodology`（设计/评审） | system-design, architecture-review |
| 前端研发 `frontend` | `frontend-engineering-methodology` | code-writing, code-deliverable, code-review |
| 后端研发 `developer` | `backend-engineering-methodology` | code-writing, code-deliverable, code-review |
| 测试专家 `qa` | `qa-methodology` | test-plan, code-testing, code-review, architecture-review（质量视角） |
| 项目经理 `main` | `coordination-methodology` | decision-record, section-review, code-deployment（协调向） |

映射实现：`backend/common/skill_methodology.py`（`TASK_DEFAULT_METHODOLOGY` + `AGENT_METHODOLOGY`）。

---

## Cursor 编排者

| id | 说明 |
|----|------|
| `coordination-methodology` | 封板→并行委派→回归→汇报（见 `.cursor/rules/project-lead.mdc`） |

---

## 新增方法论 checklist

1. 添加 `business/skills/<id>/SKILL.md`（含 frontmatter `name` / `description`）
2. 添加 `.cursor/skills/<id>/SKILL.md`（Cursor 发现）
3. 在 `skill_methodology.py` 注册 task_type / agent 映射
4. 更新对应 task skill 顶部「必须先读」
5. 添加 `backend/common/tests/test_skill_methodology.py` 用例
6. 跑 `pytest backend -q`

---

## Subagent 使用

Cursor Task / explore 子 agent 在 myteam 仓库内工作时：

- 项目级 skill 位于 `.cursor/skills/` 与 `business/skills/`
- 执行 product/arch/fe/be/qa 类任务前，先 Read 对应 methodology 文件
- **不要** 修改 `Process` / `AgentPort` / Gate 语义（见 `docs/FRAMEWORK-FREEZE.md`）

---

## 已有方法论

| id | 说明 |
|----|------|
| `system-architecture-methodology` | 约束→质量属性→trade-off→ADR→C4 |
| `product-methodology` | 问题空间→范围→R 验收→优先级 |
| `frontend-architecture-methodology` | FE 组件/状态/契约/trade-off |
| `frontend-engineering-methodology` | FE 实现→build→回归 |
| `backend-engineering-methodology` | 分层→Store→pytest |
| `qa-methodology` | 风险驱动→证据链→Gate |
| `coordination-methodology` | 编排纪律→封板→并行→回归证据 |

---

## 与「提升 agent 完成任务能力」的关系

方法论解决 **交付结构与证据纪律**；完整任务能力还需：

- workflow / templates.yaml Gate 与 task_type 对齐
- 回归脚本 exit 0 作为 submit 前置
- 上游摘要 + 定点 PATCH 改稿（Work–Review）

工业级协作 = **框架契约（内核）+ 角色方法论（skill）+ 可复现验证（回归）**。
