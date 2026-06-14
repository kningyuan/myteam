# Platform Workflow v3 — 量化 Gate 条件

> **版本**：v3.0  
> **Workflow ID**：`myteam-platform-v3`  
> **修正来源**：[`roundtable-继续-1781388407652438.md`](./roundtable-继续-1781388407652438.md) 修正项 7  
> **参照基线**：[`FRAMEWORK-FREEZE.md`](../FRAMEWORK-FREEZE.md)（封板 pytest / REG 标准）

本文定义 P1–P4 **可勾选、可证据化** 的过关条件。禁止用「所有 Gate 条件满足」等循环引用表述。

---

## 封板参照（FRAMEWORK-FREEZE.md）

| 参照项 | 封板标准 | v3 应用 |
|--------|----------|---------|
| 单元 / 集成测试 | `pytest backend -q` → **0 failed** | P3.5、P4 必跑 |
| V1 REG CHECK_ONLY | `./scripts/regression/run_regression.sh --suite v1` PASS | P3.5 建议附带 |
| E2E 分层 | `scripts/regression/tier_e2e.py` | P1.5 建基线；P3.5 扩展 ≥3 路径 |
| 内核冻结 | 不改 Process / Gate 语义 | P3 实施不得破坏封板 invariant |
| Strategy 增量区 | `business/workflows/*.yaml` | 本 workflow 即 Strategy 层交付 |

---

## P1 Gate {#p1-gate}

**任务**：`p1-gate`（@main）  
**前置交付**：P1.1 – P1.5

| # | 条件 | 量化标准 | 证据要求 |
|---|------|----------|----------|
| P1-G1 | P0 链路功能完整度 | **100%**（矩阵中 P0 行均有 v1/v2 状态 + 差距描述） | `docs/assessments/v1-v2-feature-matrix.md` |
| P1-G2 | 六维诊断 | 六维均有现状 + 差距 + 方向 | `docs/assessments/six-dimension-diagnosis.md` |
| P1-G3 | SQLite / Store 审计 | 含 state.db 大小、WAL、直写 bypass 样例、PG 价值结论 | `docs/assessments/sqlite-store-audit.md` |
| P1-G4 | 竞品基线（修正项 4） | ≥3 竞品 · ≥5 维度 · 量化数据 · URL 引用 · 差异化判断 | `docs/assessments/competitor-baseline.md`（非 TBD） |
| P1-G5 | E2E 基线（修正项 1） | ≥1 条编排内核 E2E；**双跑一致**；通过率 **100%** | `p1-5-e2e-baseline` 脚本 + 两次运行日志 |
| P1-G6 | 单元测试不退化 | `pytest backend -q` → **0 failed** | 终端输出 / CI 截图 |

**FAIL 动作**：不得启动 P2 任何任务。

---

## P2 Gate {#p2-gate}

**任务**：`p2-gate`（@main）  
**前置交付**：P2.1 – P2.5 方案文档

每个方案交付物 **必须包含** 以下六要素（修正项 7）：

1. 目标状态  
2. 当前差距  
3. 实施步骤  
4. 验收指标  
5. 风险评估  
6. 人天估算（建议项，@developer / @ops 填写）

| # | 方案任务 | 交付物路径 | 额外 Gate |
|---|----------|------------|-----------|
| P2-G1 | P2.1 API 拆分 | `docs/plans/api-split-plan.md` | 含路由边界图；供 2.3a 引用 |
| P2-G2 | P2.2 v2 迁移 | `docs/plans/v2-migration-plan.md` | P0 补齐范围与 P1.1 矩阵一致 |
| P2-G3 | P2.3a token 契约 | `docs/plans/store-token-metering-contract.md` | 抽象接口定义完整；修正项 3 |
| P2-G4 | P2.3b adapter 方案 | `docs/plans/token-adapter-plan.md` | 验收指标为**功能性三步**（修正项 2），非覆盖率 % |
| P2-G5 | P2.4 PG 迁移 | `docs/plans/pg-migration-plan.md` | 输入含 2.5 直写清单 |
| P2-G6 | P2.5 直写清单 | `docs/plans/group-manager-direct-write-inventory.md` | 每条 bypass 有收拢建议 |

**DAG 约束（修正项 3）**：

- 2.3a 依赖 2.1 路由边界图  
- 2.3b 依赖 2.3a；2.4 依赖 2.3a + 2.5；**2.3b 与 2.4 可并行**

**FAIL 动作**：不得启动 P3 执行 stub。

---

## P3 Gate {#p3-gate}

**任务**：`p3-5-regression`（@qa）为主 Gate；各 exec stub 有子 Gate

| # | 条件 | 量化标准 | 证据 |
|---|------|----------|------|
| P3-G1 | E2E 覆盖 | **≥3** 条关键路径（含 P1.5 编排内核链路） | `p3-regression-report` |
| P3-G2 | E2E 通过率 | **100%** | 同命令连续运行 0 failed |
| P3-G3 | 单元测试 | `pytest backend -q` → **0 failed** | 日志 |
| P3-G4 | token 功能性（修正项 2） | adapter 提取 → API 返回 → SSE 可验证 token | `token-metering-change-log` + 截图/日志 |
| P3-G5 | _KERNEL_RUNS（修正项 6） | Hub 重启后无 ghost `running=true` | `kernel-runs-change-log` + 复现步骤 |
| P3-G6 | 产品轻量确认（修正项 5） | P1.1 矩阵 P0 项标注「已补齐」 | `p3-2-product-light-confirm.md`（**不阻塞** P3-G1–G5） |

**P3 执行 stub 说明**：`p3-*-exec` 任务定义交付边界；Gate 以实际代码 + change-log 为准，**禁止**在 Gate 记录中预设 PASS。

---

## P4 Gate {#p4-gate}

**任务**：`p4-final-gate`（@main）  
**前置**：`p4-product-acceptance` + `p4-ops-verify` + P3.5 PASS

逐项验收清单（**禁止循环引用**）：

| # | 验收项 | 标准 | 证据路径 |
|---|--------|------|----------|
| P4-1 | P1.1 矩阵 P0 链路 | 100% 可用（产品完整验收） | `platform-v3-product-acceptance.md` |
| P4-2 | 核心用户旅程 | @product 确认可完成（修正项 5 完整层） | 同上 |
| P4-3 | API 拆分 | 按 P2.1 域边界落地；端点测试通过 | `api-split-change-log.md` |
| P4-4 | v2 P0 功能 | 与矩阵一致；轻量 + 完整验收均 PASS | 矩阵标注 + acceptance |
| P4-5 | token 计量 | 功能性三步全通 | P3-G4 证据 |
| P4-6 | _KERNEL_RUNS | 修复验证通过 | P3-G5 证据 |
| P4-7 | PG 迁移 | 测试环境验证通过 **或** 明确记录「暂不切换」及理由 | `pg-migration-change-log` + ops 报告 |
| P4-8 | E2E 回归 | ≥3 路径，100% 通过 | P3.5 报告 |
| P4-9 | 竞品基线 | 已归档且非 TBD | `competitor-baseline.md` |
| P4-10 | 封板合规 | 未破坏 Process/Gate/Adapter 隔离 invariant | arch 签字段落 |

**签发**：`p4-final-gate` 交付 `docs/reports/platform-v3-final-gate.md`，状态 **PASS** 后 v3 workflow 完结。

---

## 修正项 ↔ Gate 映射

| 修正项 | Gate 锚点 |
|--------|-----------|
| 1 E2E 基线提前 P1 | P1-G5 · P3-G1/G2 |
| 2 token 功能性验收 | P2-G4 · P3-G4 · P4-5 |
| 3 Store 先契约后实施 | P2 DAG 约束 · P2-G3/G5 |
| 4 竞品 P1 末尾 | P1-G4 · P4-9 |
| 5 轻量 + 完整验收 | P3-G6 · P4-1/2 |
| 6 _KERNEL_RUNS P3.1 附带 | P3-G5 · P4-6 |
| 7 Gate 量化 | 本文全文 + FRAMEWORK-FREEZE 参照 |
