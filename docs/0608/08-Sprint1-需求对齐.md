# Sprint 1 需求对齐（草案 — 待四路 subagent 签字）

**日期**：2026-06-08  
**前置**：Sprint 0 完成（S1~S5，56 pytest passed）  
**目标**：L1 收尾 — P0-D 孤儿回收 + P0-C2 token 计量

---

## 提议范围

### 做

| ID | 内容 | KPI |
|----|------|-----|
| P0-D | `reconcile`/settle 回收磁盘孤儿 deliverable → 过 Gate → 改判 | K4 ≥ 95% |
| P0-C2 | 定位并修复 token 计量恒 0 | K5 = 100% |
| T1 | 单元测试 + REG-04/05 脚本骨架（若可行） | pytest 覆盖 |

### 不做（本 Sprint）

- DAG 真并行（L2）
- 孤儿回收以外的 triage 改造
- 前端 UI 变更
- REG-02 全量 dogfooding（留 Sprint 1 完工后，依赖 K4/K5）

---

## 待四路确认项

1. P0-D 实现路径：B1（reconcile 扫 deliverables）是否足够？
2. P0-C2 根因：parser 已 emit step_finish，是否因墙钟删除前 result 行未到？
3. 完工门禁：是否 REG-04 + REG-05 通过即可进入 REG-02？

---

**Phase 0 已完成** → 见 [08-Sprint1-需求对齐纪要-已签字.md](./08-Sprint1-需求对齐纪要-已签字.md)
