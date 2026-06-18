# Workflow 设计评审清单

设计完成后自评；**总分建议 ≥14/18** 且 **D 节三问全 Y** 再提交 YAML。

---

## A. 项目适配（各 0–1，合计 4）— 新增

| # | 标准 | 0 | 1 | 2 |
|---|------|---|---|---|
| P1 | Goal/Done 与 workflow 一致 | 未写或矛盾 | 部分 | 逐步可追溯到 Done |
| P2 | inputs/template 已对齐 | 路径悬空 | 部分存在 | 每步【输入】【交付】可落地 |
| P3 | agent/task_type 可校验 | bootstrap 失败 | 勉强过 | ensure_workflow_ready 通过 |
| P4 | 非抄模板 | 完全照搬他项目 | 改部分 | 章节数/路径/角色已适配 |

**项目适配 ≥3/4** 才进入 B 节。

---

## B. Loop 单元六条（各 0–1，合计 6）

| # | 标准 | 0 | 1 | 2 |
|---|------|---|---|---|
| 1 | 单一 Done | 说不清 | 模糊 | 一句话可写进 description |
| 2 | 单一主交付物 | 多种混杂 | 2+ 种平权 | 1 个主 artifact |
| 3 | 输入契约 | 未写 | 口头级 | ≤3 个明确上游 |
| 4 | 失败可定位 | 整包 | 大块 | 单 step |
| 5 | 重试成本 | 必重跑全部 | 常牵连多步 | 可只 retry 一步 |
| 6 | 衔接可验证 | 无 | 模糊 | 1–2 条可核对项 |

---

## C. 三维（各 0–2，合计 6）

### 边界维

- **0**：step 重叠或 Done 冲突  
- **1**：能跑但常「顺便做别的」  
- **2**：每步名词+动词清晰  

### 验收维

- **0**：无 review 收口  
- **1**：仅有 L1 或仅有 L2  
- **2**：template + review 步 + transition 完整  

### 经济维

- **0**：步数过多或过少  
- **1**：Hub 价值一般  
- **2**：pause/retry 有意义，预期 1–3 轮收敛  

---

## D. YAML 契约（各 0–2，合计 6）

| 检查项 | 0 | 2 |
|--------|---|---|
| 未写 skills / 未强制 Read SKILL | 有 | 无 |
| `split_enabled` 与静态步一致 | true 且无理由 | false |
| `load_workflow` + `ensure_workflow_ready` | 失败 | 通过 |
| loop transition PASS/FAIL/exhaust | 缺失 | 完整 |
| description 四段 | 混乱 | 统一 |
| 章节在 YAML 不在孤立大纲 | 仅大纲 | YAML 为准 |

---

## E. 快速三问（必须全 Yes）

1. FAIL 时能否只 retry **一个** step id？  
2. PASS 后下游能否 **只读 deliverables** 开工？  
3. 新人只看 workflow + deliverables 能否说清每步干什么？  

---

## 记录模板

```text
Workflow: <id>  version: <x.y>
Archetype: <work-review-round | doc-plan-static | custom>
适配: __/4  六条: __/6  三维: __/6  契约: __/6  合计: __/22
三问: Y / Y / Y
备注:
```
