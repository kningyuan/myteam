# myteam-platform-v3 Workflow

> **ID**：`myteam-platform-v3`  
> **版本**：3.0  
> **状态**：可执行定义（非已完成交付）  
> **修正项**：7 项见 [`docs/assessments/roundtable-继续-1781388407652438.md`](../../docs/assessments/roundtable-继续-1781388407652438.md)  
> **Gate 手册**：[`docs/assessments/platform-v3-gates.md`](../../docs/assessments/platform-v3-gates.md)

---

## 阶段概览

```text
P1 诊断 ──gate──▶ P2 方案 ──gate──▶ P3 执行（并行）──▶ P4 验收
  │                    │                  │
  ├ P1.1 功能矩阵      ├ P2.1 API 方案     ├ P3.1 API 拆分 + _KERNEL_RUNS
  ├ P1.2 六维诊断      ├ P2.2 v2 方案      ├ P3.2 v2 补齐 → P3.2b 产品轻量确认
  ├ P1.3 SQLite 审计   ├ P2.3a/3b token    ├ P3.3 token 计量
  ├ P1.4 竞品基线      ├ P2.4 PG 方案      ├ P3.4 PG 迁移
  └ P1.5 E2E 基线      └ P2.5 直写清单     └ P3.5 回归 → P4
```

**Roster**：main · arch · product · research · developer · qa · ops

---

## 启动前检查

```bash
cd /path/to/myteam
export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend"

# 1) Workflow 定义合法
venv/bin/python3 -m pytest backend/common/tests/test_workflow_loader.py -q -k myteam-platform-v3

# 2) 封板基线（FRAMEWORK-FREEZE）
venv/bin/python3 -m pytest backend -q

# 3) 竞品模板存在（P1.4 将填充）
test -f docs/assessments/competitor-baseline.md
test -f docs/assessments/platform-v3-gates.md
```

---

## CLI 启动

```bash
export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend"

GOAL=$(cat <<'EOF'
myteam 平台架构改进 Workflow v3：
按 business/workflows/myteam-platform-v3.yaml 执行 P1→P4；
严格遵守 docs/assessments/platform-v3-gates.md 量化 Gate；
P1 完成前不得进入 P2；禁止伪造 PASS 或预设已完成实施。
EOF
)

venv/bin/python3 backend/common/run_kernel.py platform-v3-$(date +%Y%m%d) \
  --workflow myteam-platform-v3 \
  --title "Platform v3 架构改进" \
  --goal "$GOAL" \
  --budget 2000000 \
  --backend claude
```

**Resume**（中断后续跑）：

```bash
venv/bin/python3 -c "from common.run_kernel import resume_project; \
  resume_project('platform-v3-YYYYMMDD', backend='claude')"
```

---

## Hub 启动

1. Hub → 新建项目 → Workflow 选择 **`myteam-platform-v3`**
2. Goal 粘贴上文 `GOAL` 或链接本 README
3. Budget 建议 ≥ 2_000_000 tokens（P3 并行扇出）
4. Backend 生产基线：`claude`（见 `docs/PRODUCTION_BASELINE.md`）

---

## 关键交付物路径

| 阶段 | 路径 |
|------|------|
| P1 诊断 | `docs/assessments/*` |
| P2 方案 | `docs/plans/*` |
| P3 实施记录 | `docs/executions/*` |
| P4 报告 | `docs/reports/*` |
| 竞品基线（P1.4） | `docs/assessments/competitor-baseline.md` |

---

## 并行与依赖要点

| 规则 | 说明 |
|------|------|
| P2 并行 | P2.1 与 P2.5 可在 P1 gate 后并行；2.3b ∥ 2.4（共享 2.3a 契约） |
| P3 并行 | `parallel_enabled: true`，max 4；P3.2b 轻量确认**不阻塞** P3.3/P3.4 |
| 修正项 6 | `_KERNEL_RUNS` 修复写入 P3.1 description，不占 P2 slot |
| 修正项 4 | 竞品基线不阻塞 P2 技术任务启动 |

---

## 验收

最终 PASS 以 `p4-final-gate` 交付 `docs/reports/platform-v3-final-gate.md` 为准，逐项对照 [`platform-v3-gates.md#p4-gate`](../../docs/assessments/platform-v3-gates.md#p4-gate)。
