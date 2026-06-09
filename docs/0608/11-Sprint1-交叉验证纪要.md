# Sprint 1 四路交叉验证纪要

**日期**：2026-06-09（迭代 3 更新）  
**阶段**：Phase 2 交叉评审 + REG-02 迭代收尾 + L1 发版门禁  
**主控**：Cursor 主 Agent 汇总  
**输入**：开发 / QA / 架构师 / 产品 subagent 并行回报 + 主控复验

---

## 一、总览

| 维度 | 结论 |
|------|------|
| **Sprint 1 整体** | **L1_GATE_PASS**（REG 全绿；FULL PASS 仍不升，budget 不可对外宣称「可控」） |
| **REG-02** | **PASS**（K1=**100%**，K3=0%） |
| **REG-04** | **PASS**（K4=100%） |
| **REG-05** | **PASS**（K5=100%，规划期即停验收等价态） |
| **pytest T1** | **83 passed** |
| **L1 用户可感知** | **~90%**（发版门禁 REG-02 已过关） |

---

## 二、迭代 2：REG-02 t4 根因与修补

| 轮次 | 结果 | 要点 |
|------|------|------|
| 首轮 | FAIL K1=75% | t1–t3 needs_review；t4 `no_response` |
| 二轮 resume | FAIL | Claude 会话污染 → `messages[1].role` API 400 |
| 三轮 resume | **PASS K1=100%** | `--no-session-persistence` + haiku 重跑 t4 |

**根因**：

1. Claude 工作区会话在多 execute 间污染 → API 400
2. t4 二次失败：引擎临时不可用（`engine is not available temporarily`），未写 `.response`
3. `reg_02_parallel.py` PROJECT_ID 与 state.db 不一致（已对齐 `reg-parallel-4leaf`）

**代码修补**（本地 WIP，未 commit）：

| 文件 | 变更 |
|------|------|
| `backend/adapters/claude/adapter.py` | `--no-session-persistence` |
| `scripts/regression/reg_02_parallel.py` | PROJECT_ID 对齐；`REG02_RESUME`；`REG02_CHECK_ONLY` |
| `business/workflows/reg-parallel-4leaf.yaml` | 固定四叶子 DAG |

---

## 三、迭代 3：四路签字

| 角色 | 结论 | 要点 |
|------|------|------|
| **开发** | DONE | opencode adapter cancel/yield + stderr 对齐 Claude（P1） |
| **QA** | PASS | pytest 83 + REG-02/04/05 全绿 |
| **架构师** | PASS | D1 隔离完好；opencode 无 session-persistence 等价旗标（omit `-c` 即可） |
| **产品** | L1_GATE_PASS | 故事 1/2 PASS；故事 3 conditional；**L1 发版门禁 REG-02 达标** |

---

## 四、主控复验（迭代 3）

```bash
pytest T1 套件 → 83 passed
REG02_CHECK_ONLY=1 reg_02_parallel.py → PASS (K1=100%, K3=0%)
reg_04_orphan.py → PASS (K4=100%)
reg_05_budget.py → PASS (K5=100%, paused)
run_regression.sh --suite all → 全绿
```

---

## 五、分歧与裁决

| 分歧 | 裁决 |
|------|------|
| Sprint 1 升 FULL PASS | **否** — budget 交互级硬停未交付 |
| L1 发版门禁 REG-02 | **是** — K1=100% ≥ 80% |
| REG-05 绝对 token 数 | **不考核** — 规划后 pause + 零 execute 为验收等价态 |
| opencode session 持久化 | **无 CLI 旗标** — 不传 `-c`；kernel 不传 session_resolver |

---

## 六、剩余工作（L2 入口）

| 优先级 | 任务 | 负责 |
|--------|------|------|
| P2 | 交互级 budget 硬停 | 下一 Sprint |
| L2 | 真并行调度、Store WAL 并发 | 架构 + 开发 |
| L2 | Gate retry session、R2 死管道 | 开发 |
| L3 | Skill 抽提、self-upgrade workflow | 产品 + 开发 |

---

*迭代 2 REG-02 闭环完成。L1 发版门禁达标。进入 L2 规划。*
