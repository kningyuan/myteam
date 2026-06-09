# Sprint 1 功能预期对齐纪要

**日期**：2026-06-09（迭代 3 更新）  
**阶段**：Phase 3 完工门禁 — **L1_GATE_PASS**  
**主控**：Cursor 主 Agent 汇总  
**前置**：`08-Sprint1-需求对齐纪要-已签字.md`（Phase 0）、Phase 1 实施、Phase 2 四路交叉评审

---

## 一、Sprint 1 结论

| 维度 | 结论 |
|------|------|
| **整体** | **L1_GATE_PASS** — REG-02/04/05 PASS；pytest T1 83 passed |
| **可演示** | 孤儿回收；token 计量；budget pause；四叶子 workflow dogfooding（K1=100%） |
| **不可宣称** | Sprint 1 FULL PASS（budget 交互级硬停未交付）、历史 token 回填、独立运行报告 |

---

## 二、Phase 0 验收对照

### P0-C2（token 计量）

| 项 | 阈值 | 结果 | 证据 |
|----|------|------|------|
| `_extract_tokens` input+output 回退 | pass | **pass** | `agent_port._extract_tokens` + `test_extract_tokens_input_output_fallback` |
| Claude result 无 total | pass | **pass** | `test_result_without_total_tokens_uses_input_plus_output`、`test_meters_claude_result_tokens_without_total` |
| grace 排空迟到 step_finish | pass | **pass** | `test_grace_window_drains_late_step_finish` |
| done 路径 tokens > 0 | pass | **pass** | `test_transport_forwards_events_and_meters_tokens` 等 |
| K5 = 100% | 100% | **pass** | REG-05 `reg_05_budget.py`（规划期 pause） |

### P0-D（孤儿回收）

| 项 | 阈值 | 结果 | 证据 |
|----|------|------|------|
| timed_out + 合法 .response → 采纳 | pass | **pass** | `test_reconcile_adopts_timed_out_orphan`、`test_resume_adopts_timed_out_orphan` |
| 不合规孤儿保持 failed/timed_out | 100% | **pass** | `test_reconcile_keeps_timed_out_without_valid_response`、`test_resume_keeps_timed_out_when_orphan_invalid` |
| gc 竞态防护 | pass | **pass** | `gc_terminal` / `gc_orphan` 跳过可采纳响应；`test_gc_skips_timed_out_with_adoptable_response` |
| reconcile→settle 主路径 | pass | **pass**（Phase 2 后修补） | `resume_project` gc 移至 settle 之后；`test_kernel_order_reconcile_gc_then_resume_settles` |
| K4 ≥ 95% | ≥95% | **pass** | REG-04 K4=100% |

### T1（测试）

| 项 | 结果 |
|----|------|
| 孤儿正向/负向 | **pass** |
| token Store 持久化 | **pass** |
| gc 防回归 | **pass** |
| Sprint 1 相关 pytest | **83 passed**（含主控修补后 `test_recovery`） |

### 完工门禁

| 门禁 | 结果 |
|------|------|
| 新增 pytest 全绿 | **pass** |
| REG-02 pass | **pass** | K1=100%（`reg_02_parallel.py`） |
| REG-04 pass | **pass** | K4=100% |
| REG-05 pass | **pass** | K5=100%，规划期 pause |

---

## 三、用户故事对照（产品签字）

| # | 用户故事 | 结果 | 说明 |
|---|----------|------|------|
| 1 | 崩溃重启后合法成果自动回收 | **pass** | `reconcile_on_start` + `settle_in_progress_task` + `resume_project` 顺序已闭环 |
| 2 | Hub/obs 显示非零 token | **pass**（新运行） | 计量链单测 OK；**旧 interaction 不回填** |
| 3 | budget 护栏对新运行有数据可依 | **conditional** | REG-05 PASS（规划期 pause）；交互级硬停未交付 |
| 4 | 运行报告有交付物 + 成本证据 | **conditional** | Obs 多 API 组合视图，无独立报告端点 |

---

## 四、四路 Phase 2 评审结论

| 角色 | 结论 | 关键意见 |
|------|------|----------|
| **架构师** | CONDITIONAL_PASS → **修补后 pass** | 发现 `reconcile→gc→settle` 断链 P0；主控已修 `run_kernel.resume_project` gc 顺序 + `gc_orphan` 对称守卫 |
| **产品主控** | CONDITIONAL_PASS | 核心价值兑现；勿宣称 KPI/REG-02；REG-04 文档口径需与签字一致 |
| **QA** | CONDITIONAL_PASS | T1 82→83 passed；REG 脚本脚手架未落地 |
| **开发** | CONDITIONAL_PASS | Step 1–3 ✅；Step 4 REG 待跑；grace 2.5s 当前足够 |

---

## 五、主控裁决（Phase 2 分歧）

| 分歧 | 裁决 | 处置 |
|------|------|------|
| reconcile 采纳后 gc 删盘导致 settle 失败 | **采纳架构师 P0** | `run_kernel.resume_project`：`gc_workspace` 移至 `proc.resume()` 之后；`resume_in_progress_projects` 去掉启动时 gc |
| gc_orphan 与 gc_terminal 策略不对称 | **采纳开发建议** | `gc_orphan_workspace_files` 对 timed_out/failed 可采纳响应跳过删除 |
| REG-04 按 deliverables 还是 .response | **维持 Phase 0** | REG-04 脚本按 `.response` + reconcile/settle，**不**扫 deliverables |
| Sprint 1 是否可宣称完工 | **CONDITIONAL_PASS** | 代码+单测达标；REG-04/05 通过后升为 PASS |

---

## 六、实现清单（Phase 1 交付物）

| 文件 | 变更摘要 |
|------|----------|
| `backend/common/agent_port.py` | `_extract_tokens` 回退；`reconcile_on_start` 含 timed_out |
| `backend/common/task_pipeline.py` | `settle_in_progress_task` timed_out 采纳 + 防双写 |
| `backend/common/workspace_gc.py` | gc_terminal / gc_orphan 跳过可采纳孤儿 |
| `backend/common/run_kernel.py` | resume 路径 gc 顺序修正（Phase 2 主控修补） |
| `backend/common/tests/*` | T1 正/负例、token、gc、kernel 顺序 |

| `backend/adapters/claude/adapter.py` | `--no-session-persistence`（REG-02 t4 修补） |
| `backend/adapters/opencode/adapter.py` | cancel/yield + stderr 对齐 Claude（P1） |
| `scripts/regression/reg_02_parallel.py` | REG-02 E2E + KPI 检查 |

**未纳入 Sprint 1**：DAG 真并行、前端 UI、历史 token 回填、交互级 budget 硬停。

---

## 七、L2 入口条件（已满足 L1）

- [x] REG-04 / REG-05 / REG-02 全绿
- [x] pytest T1 83 passed
- [ ] 交互级 budget 硬停（P2，可并行 L2 内核）
- [ ] L2 发版门禁：Level-2 三角色并行评审项目

---

## 八、签字区（Phase 3）

| 角色 | 结论 | 签字 |
|------|------|------|
| 产品主控 | CONDITIONAL_PASS | ✅ 用户故事 1–2 可演示；3–4 绑 REG |
| 架构师 | CONDITIONAL_PASS | ✅ P0 断链已修；adapter 隔离完好 |
| QA | CONDITIONAL_PASS | ✅ T1 全绿；REG 待执行 |
| 开发 | CONDITIONAL_PASS | ✅ 实施清单完成 |
| **主控** | **L1_GATE_PASS** | ✅ REG 全绿；L1 发版门禁达标 |

---

*Sprint 1 L1 发版门禁达标。FULL PASS 待交互级 budget 硬停。L2 见 `00-升级总路线图.md`。*
