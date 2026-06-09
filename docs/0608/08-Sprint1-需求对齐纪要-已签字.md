# Sprint 1 需求对齐纪要（已签字）

**日期**：2026-06-08  
**阶段**：Phase 0 开工门禁 — **已通过**  
**主控**：Cursor 主 Agent 汇总  
**前置**：Sprint 0 完成（56 pytest passed）

---

## 一、范围冻结

### 本 Sprint 做

| ID | 内容 | 负责人 | KPI |
|----|------|--------|-----|
| P0-D | 扩展 `reconcile_on_start` 覆盖 `timed_out` interaction；`settle_in_progress_task` 补 timed_out 采纳路径；开工前核查 `gc_workspace` 竞态 | 开发 | K4 ≥ 95% |
| P0-C2 | `_extract_tokens` 增加 input+output 回退；grace 窗口延长或 cancel 前完整 drain；抓真实 Claude result 行验证 parser | 开发 | K5 = 100%（done/needs_review） |
| T1 | 新增 pytest：孤儿正向/负向、token Store 持久化 | 开发+QA | 全绿 |

### 本 Sprint 不做

- DAG 真并行、triage 改造、前端 UI、REG-02 dogfooding、token 预算告警、历史数据回填

---

## 二、四路签字

| 角色 | 结论 | 条件（已纳入实施） |
|------|------|-------------------|
| **产品主控** | 有条件同意 → **同意** | K4 分母=本 run 产生的孤儿；不承诺 UI |
| **架构师** | 有条件同意 → **同意** | 先查 gc 竞态；parser 修前对照真实 result JSON |
| **QA** | 有条件同意 → **同意** | 负例测试必填；Store 持久化链测试必填 |
| **开发** | 有条件同意 → **同意** | task status guard 防双写；fallback 单路径实现 |

---

## 三、分歧与主控裁决

| 分歧 | 裁决 |
|------|------|
| P0-D：扫 deliverables 目录 vs 扩 timed_out SQL | **扩 timed_out SQL + settle 路径**（开发/架构一致）；不另扫 deliverables |
| reconcile 触发时机 | **`run_kernel` 启动时** `reconcile_on_start`；resume 链路同 |
| P0-C2 根因 | **非墙钟**；主因 `_extract_tokens` 无回退 + grace 丢 result 行 |
| REG-02 时机 | Sprint 1 完工（REG-04/05 + pytest）**后**再跑 |

---

## 四、用户故事（产品签字）

1. 任务崩溃后重启，合法成果被自动回收，无需全量重跑
2. Hub/obs 显示**非零** token，成本可见
3. budget 护栏对**新运行**有数据可依
4. 运行报告有交付物 + 成本证据

---

## 五、验收标准（QA 签字）

### P0-D

| 项 | 阈值 |
|----|------|
| 正向：timed_out + 合法 .response → 采纳 | pass |
| 负向：不合规孤儿 → 保持 failed | 100% |
| K4 | ≥ 95% |

### P0-C2

| 项 | 阈值 |
|----|------|
| `status=done/needs_review` 的 interaction | tokens > 0 |
| K5 | 100%（正常完成路径） |
| budget 超限 | 可中断（REG-05 本地 E2E） |

### 完工门禁

1. 新增 pytest 全绿
2. REG-04 pass
3. REG-05 pass（有 CLI 环境时；无则标记本地验收）

---

## 六、功能预期（Phase 3 对照基准）

> Sprint 1 成功 = 模拟崩溃后重启，孤儿响应被回收且 Gate 负例不误升；新运行 interaction 的 tokens 在 Store 中非零；REG-04/05 通过。

**Phase 3 完工时**，四路须对照本节逐项确认 pass/fail。

---

## 七、实施顺序（开发签字）

```
Step 1  P0-C2（_extract_tokens + grace）
Step 2  核查 gc_workspace 竞态
Step 3  P0-D（timed_out reconcile + settle）
Step 4  pytest 全量 + REG-04/05
```

---

*Phase 0 完成。开发 subagent 可进入 Phase 1 实施。*
