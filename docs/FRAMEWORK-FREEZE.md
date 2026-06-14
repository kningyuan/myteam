# 框架封板声明（Framework Freeze）

> **版本**：2026-06-10  
> **状态**：L1/L2 System Kernel + Hub 集成 **已封板**  
> **验证**：`PYTHONPATH=backend venv/bin/python3 -m pytest backend -q` → **470 passed**  
> **V1 REG**：`./scripts/regression/run_regression.sh --suite v1` → CHECK_ONLY PASS

---

## 1. 封板含义

自本版本起：

| 层级 | 策略 |
|------|------|
| **System Kernel** | 不再做大重构；仅修 bug、安全与可观测性小补丁 |
| **Hub 集成** | 同上；adapter 隔离 invariant 不得破坏 |
| **Strategy / Skill** | **主增量区** — 新增 workflow、task_type、Skill、回归剧本 |

**目标**：使用者只需在 **使用层** 定制 `business/workflows/*.yaml` 与 `business/skills/*/SKILL.md`，无需改 `Process` / `AgentPort` / `Gate`。

---

## 2. 已封板能力（代码实证）

### 2.1 编排内核

- 七种 interaction：`team_config` / `task_plan` / `evaluate` / `execute` / `review` / `triage`
- DAG 波次调度 + 可选 `parallel_enabled` / `split_enabled` / `review_enabled`
- `plan_gate` + `Gate` + `submit_result` 契约链（无 JSON rescue）
- `AgentPort` 看门狗、预算、孤儿响应 reconcile
- Workflow 加载跳过即兴规划；自由规划走 LLM `task_plan`

### 2.2 Hub 集成（2026-06-10 修复）

- **Workflow 选项合并**：Hub 预传 `ProcessConfig` 时，`run_project` 仍合并 workflow 的 `parallel_enabled` / `review_enabled` / `split_enabled` / `skill_extract_enabled`（`run_kernel.py`）
- **Adapter 隔离**：`stream_fanout` / `notify_service` / `group_manager` 仅消费规范化 `thinking` SSE，不解析 opencode 原始字段

### 2.3 确定性推导 vs LLM 规划

| 入口 | 机制 | 用途 |
|------|------|------|
| Hub「自动推导」 | `workflow_suggest.py` 关键词模板 | 编辑页快速起草 DAG |
| 内核自由规划 | `main` + CLI `task_plan` + `plan_gate` | 运行时即兴拆任务 |
| 固定 workflow | `business/workflows/*.yaml` | **推荐生产路径** |

---

## 3. 磁盘上的 Strategy 资产（当前）

`business/workflows/` 内 **4 条** 中文 workflow：

| ID | 场景 |
|----|------|
| `GitHub项目调研` | 三视角并行调研 + 汇总 |
| `GEO优化` | GEO 审计→改稿→验证 |
| `内容运营` | 调研→内容→发布 |
| `数据分析` | 需求→分析→报表→验收 |

新增场景：**复制 yaml + 配 Skill**，见 [`business/workflows/README.md`](../business/workflows/README.md)。

---

## 4. 明确不在封板范围（L3 脚手架，按需启用）

以下代码存在但 **未闭合生产环**，不阻塞业务 workflow 交付：

| 能力 | 状态 | 说明 |
|------|------|------|
| `Store.memory` RAG 注入 | 写多读少 | recurring 用进程内 `prior_summary` |
| `workspace_event` 总线 | 未启动 ProjectionRunner | Hub 仅 @mention 写入 |
| `skill_extract` | scaffold | 截断草稿，非 LLM 蒸馏 |
| `self-upgrade` workflow | 未提供 yaml | `reg_l3_self_upgrade.py` CHECK_ONLY 可报缺 |

**原则**：业务需要时再补 Skill/workflow，不为此改内核。

---

## 5. 使用层定制清单（后续唯一主战场）

### 5.1 新增业务场景（标准步骤）

1. 在 `business/templates/templates.yaml` 注册所需 `task_type`（若尚未存在）
2. 编写 `business/workflows/<场景>.yaml`（roster、tasks、dependencies、options）
3. 编写 `business/skills/<场景>/SKILL.md`（阶段 SOP、检查清单）
4. 本地校验：`pytest backend/common/tests/test_workflow_loader.py -q`
5. 可选：`scripts/regression/reg_<场景>.py` 发版门禁

### 5.2 发起项目

```bash
export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend"
venv/bin/python3 backend/common/run_kernel.py <project_id> \
  --workflow <workflow_id> \
  --goal "…" --budget 1000000 --backend claude
```

Hub：选 workflow → 填 goal → 运行（workflow options 与 CLI 行为一致）。

### 5.3 禁止事项（破坏封板）

- 在 `hub/services` 解析 CLI 专有字段
- 在 `Process` 引入 JSON rescue / 绕过 Gate
- 仅靠 Skill 让内核识别新 task（必须先写 `templates.yaml`）

---

## 6. 回归与发版

```bash
# 单元 + 集成（必跑）
PYTHONPATH=backend venv/bin/python3 -m pytest backend -q

# 分层 E2E（需 claude CLI，慢）
PYTHONPATH=backend venv/bin/python3 scripts/regression/tier_e2e.py

# L2 并行门禁（需 claude CLI 或 CHECK_ONLY）
REG_L2_CHECK_ONLY=1 PYTHONPATH=backend python3 scripts/regression/reg_l2_3role.py
```

---

## 7. 相关文档

- 架构：[`docs/ARCHITECTURE.md`](./ARCHITECTURE.md)
- 金路径：[`docs/0608/15-标准协作模式总结.md`](./0608/15-标准协作模式总结.md)
- Workflow 编写：[`business/workflows/README.md`](../business/workflows/README.md)
- Invariant：仓库根 [`CLAUDE.md`](../CLAUDE.md)
