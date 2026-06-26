---
name: 协作方法论
description: 多 Agent 编排纪律：范围封板、并行委派、回归验证与集成汇报，适用于项目经理与阶段闸门任务。
---
# 编排纪律（Coordination Methodology）

> **适用**：myteam `main`（项目经理）、Cursor 侧总协调 Agent、阶段决策与部署签发类任务。  
> **不适用**：领域交付（PRD、代码、测试）— 用各角色 `*-methodology`，勿用本 skill 代替。

**myteam 红线**：读 `docs/FRAMEWORK-FREEZE.md`。编排者的职责是 **保框架稳定、保回归通过**，不是亲自写完全部领域产出。

---

## 何时启用

- 拆多 agent / 多 subagent 并行升级或交付
- `task_type=decision-record` 且 `agent_id=main`
- `code-deployment`、阶段闸门汇总、验收签发
- 用户要求「全面升级 myteam 但不动内核契约」

---

## Step 1 — 意图与范围（5 分钟内写清）

| 维度 | 必须回答 |
|------|----------|
| 目标 | 本轮要达成什么可验证结果 |
| In scope | 允许改动的目录/文件类型 |
| Out of scope | **明确** Process / AgentPort / Gate / Store 语义、未授权 git 操作 |
| 成功标准 | 例如 pytest N passed、regression exit 0、具体 deliverable Gate |

**禁止**在未写 Out of scope 前派 subagent 改内核。

---

## Step 2 — 封板检查（Hard Stop）

改动前确认：

- [ ] 是否触及 `backend/common/process.py`、`agent_port.py`、`plan_gate.py` 调度语义？
- [ ] 是否改变 `submit_result` / Interaction 契约？
- [ ] 是否破坏 Hub adapter 隔离 invariant？

任一项为「是」且无用户 **明示授权** → **停止**，仅写方案不落地。

**主增量区**（鼓励）：`business/workflows/`、`business/skills/`、`docs/`、Hub routes 模块化、frontend、回归脚本。

---

## Step 3 — 并行委派（Subagent 纪律）

### 3.1 何时并行

| 条件 | 做法 |
|------|------|
| 域独立（产品 skill / 前端 skill / 后端 skill / 测试 / 文档） | 并行 subagent |
| 同一文件或同一契约链 | 串行或单 agent |
| 需全库 grep 摸底 | 1 个 explore agent，再分域实施 |

### 3.2 每个 subagent 任务包须含

1. **Workspace 绝对路径**
2. **角色与方法论**：必须先读的 `business/skills/<role>-methodology/SKILL.md`
3. **禁止项**：不得改 Process/AgentPort/Gate
4. **验证命令**：`PYTHONPATH=backend venv/bin/python3 -m pytest backend -q` 或更窄路径
5. **返回格式**：改了哪些文件、测试结果、遗留 gap

### 3.3 Subagent 不应做的事

- 不各自跑 destructive git
- 不重复改同一文件（编排者合并冲突）
- 不宣称 PASS 而无命令输出

---

## Step 4 — 集成与回归（Evidence Before Claims）

合并 subagent 产出后 **编排者亲自**：

```bash
cd myteam
PYTHONPATH=backend venv/bin/python3 -m pytest backend -q
# 若动 business/config 或 skill 脚本：
bash scripts/regression/run_regression.sh --suite unit
```

- pytest 数量 **不得少于** 合并前基线（除非有 intentional 删除且说明）
- 失败 → 指派修复 subagent 或自行最小 fix，**禁止**带 failing 测试结束本轮

---

## Step 5 — 汇报与遗留

交付编排结论须含：

| 块 | 内容 |
|----|------|
| 已完成 | 文件/能力 + 测试证据 |
| 框架 | 明确「未改内核契约」或列出例外 |
| 遗留 | 下一阶段的 gap（给领域 agent，不是编排者代写） |
| 第 3 阶段 | 「完整任务能力」待办（若本轮只做 1+2） |

---

## 与领域方法论的分工

```text
编排者（本 skill）     → 谁做、何时并行、如何验收、封板
领域 *-methodology   → 怎么做 PRD / 代码 / 测试 / 架构
task skill             → 具体 SOP 与模板章节
内核                   → Process / AgentPort / Gate（编排者不碰）
```

Cursor 会话：读 `.cursor/skills/coordination-methodology/SKILL.md` + `.cursor/rules/project-lead.mdc`。  
myteam：`main` 须在 `agents_registry.json` 的 `skills` 中显式挂载 `coordination-methodology`（及所需其它 skill）；内核不再按 task_type 隐式注入。

---

## 反模式（禁止）

- 编排者自己写完所有领域 diff 却不跑 pytest
- 5 个 subagent 同时改 `agent_transport.py`
- 用「应该没问题」代替 regression exit 0
- 为赶进度跳过 FRAMEWORK-FREEZE
