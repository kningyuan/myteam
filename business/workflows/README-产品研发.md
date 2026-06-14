# 产品研发 workflow

> workflow id：`产品研发` · P0 完整研发链

## 任务链

```text
t-req (requirements/product)
  → t-arch (architecture-review/arch)   # 大需求保留；小需求可在 YAML 删此节点
  → t-dev (code-writing/developer)
  → t-test (code-testing/qa)
  → t-acc (acceptance-report/product)
```

## 选项

| 选项 | 值 | 说明 |
|------|-----|------|
| `needs_review_blocks` | `false` | Gate 通过后不因自评 needs_review 挡下游 |
| `review_enabled` | `false` | 评审由各 task_type Gate 承担 |

## OpenCode 试跑（已验证）

**项目**：`p0-opencode-trial` · **状态**：`completed` · **日期**：2026-06-11

```bash
export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend"
GOAL=$(cat business/workflows/p0-opencode-goal.txt)

venv/bin/python3 backend/common/run_kernel.py p0-opencode-trial \
  --workflow 产品研发 \
  --title "P0产品研发-OpenCode试跑" \
  --goal "$GOAL" \
  --budget 800000 \
  --backend opencode
```

**产出摘要**：

- `deliverables/t-req_deliverable.md` — PRD
- `deliverables/t-arch_deliverable.md` — 架构评审
- `deliverables/t-dev/` — `workflow_validate.py` + 测试
- 已合并进仓库：`backend/common/workflow_validate.py`、`backend/hub/api/server.py` 前置校验

**REG 验收**：

```bash
REG_P0_PROJECT_ID=p0-opencode-trial REG_REQUIRE_LIVE_KPI=1 \
  MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \
  venv/bin/python3 scripts/regression/reg_p0_product_dev.py
```

## Resume

若中途中断：

```bash
venv/bin/python3 -c "from common.run_kernel import resume_project; \
  resume_project('p0-opencode-trial', backend='opencode')"
```
