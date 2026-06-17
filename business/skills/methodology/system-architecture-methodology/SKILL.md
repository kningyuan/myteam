---
name: "系统架构方法论"
task_type: system-architecture-methodology
description: >-
  系统架构方法论：约束→质量属性→候选模式→trade-off→ADR→C4 边界图。
  system-design / architecture-review 必须先读本 skill。
---
# 系统架构方法论（myteam 适配版）

> **来源合成**（可复用、已裁剪）：
> - [awesome-cursor-skills / architecture-decision-records](https://github.com/spencerpauly/awesome-cursor-skills)
> - [wshobson/agents / architecture-patterns](https://github.com/wshobson/agents)（Hexagonal / Ports）
> - C4 Model Context+Container 精简层（非全量 bottom-up 工作流）

**myteam 红线**：读 `docs/FRAMEWORK-FREEZE.md`；禁止建议重写 `Process` / `AgentPort` / Gate 调度语义；Store 真相、Adapter 边界不变。

---

## 何时启用

- `task_type=system-design` 或 `architecture-review`
- 用户问「用什么架构模式」「有没有理论依据」
- 任何需要 **在 2+ 方案间做显式 trade-off** 的技术决策

---

## 执行流程（必须按序）

### Step 1 — 问题与约束（5–10 行）

写清：

| 维度 | 内容 |
|------|------|
| 目标 | 要解决什么用户/系统问题 |
| 范围 | 在系统哪一层（Kernel / Hub / Frontend / 全栈） |
| 硬约束 | 部署形态、团队规模、现有技术栈、封板 invariant |
| 非目标 | 明确不做的事 |

**禁止**在未写约束前推荐模式。

### Step 2 — 质量属性优先级（选 3–5 项并排序）

从下列选取并 **1=最高优先级**：

- 可维护性 / 可测试性 / 可演进性
- 性能 / 可用性 / 安全
- 开发效率 / 运维复杂度 / 成本

输出表格：`属性 | 优先级 | 本任务为何重要`。

### Step 3 — 候选架构模式（至少 2 个）

从模式库选 **≥2** 个真正可行的候选（不要凑数）：

| 模式 | 适用信号 |
|------|----------|
| **分层架构** | CRUD + 清晰上下层，变更集中在接口 |
| **六边形 / Ports & Adapters** | 需替换实现（DB、CLI、SSE 后端）且核心稳定 |
| **模块化单体** | 单部署单元，但要域边界清晰（Hub routes 拆分） |
| **事件驱动** | 多订阅者、异步扇出、解耦时间线 |
| **CQRS 读写分离** | 读模型与写模型压力/形状差异大 |

每个候选写：**一句话描述 + 主要优点 + 主要代价**。

### Step 4 — Trade-off 矩阵（Gate 硬要求）

`templates.yaml` 的 `system-design` 要求交付物含 **trade-off**。使用：

```markdown
| 选项 | 满足的质量属性 | 牺牲的质量属性 | 复杂度 | 与 myteam 现状契合 |
|------|----------------|----------------|--------|-------------------|
| A    | …              | …              | 低/中/高 | …                 |
| B    | …              | …              | …      | …                 |
```

**选定方案**一行结论 + **不选其他的首要理由**（各 1 句）。

### Step 5 — C4 精简（Context + Container）

交付 **Mermaid** 两张图（或等价文字表）：

1. **Context**：人/外部系统 ↔ 本系统边界
2. **Container**：本系统内主要容器（Hub、Kernel、Store、Frontend、Adapter）及关系

不要陷入 Code 级全量 C4，除非 task 明确要求。

### Step 6 — ADR（每个重大决策 1 条）

重大决策 = 难 reversal、跨模块、6 个月后会被问「为什么」。

写入 `docs/decisions/NNN-<slug>.md`，模板见 `references/adr-template.md`。

在 system-design 交付物 **架构方案** 节引用：`ADR-NNN`。

---

## architecture-review 专用

在评审报告中额外输出：

1. **现状架构快照**（C4 Container 级，基于代码扫描，非想象）
2. **发现项** 映射到质量属性缺口
3. **演进建议** 必须附 trade-off；P0/P1/P2 分级

---

## 反模式（禁止）

| 反模式 | 正确做法 |
|--------|----------|
| 直接给唯一方案 | 至少 2 候选 + trade-off |
| 堆术语无约束 | 先写 Step 1 约束 |
| 建议重写内核 | 在 Hub/Skill/Store 端口层演进 |
| 无验证的 scalability 断言 | 写「当前约束下足够/不足」+ 触发升级条件 |
| ADR 写成长篇设计 doc | ADR 只 capture **决策**，设计放交付物 |

---

## 验证清单（自检）

- [ ] 有约束表
- [ ] 有质量属性优先级
- [ ] ≥2 候选模式
- [ ] 有 trade-off 矩阵 + 选定理由
- [ ] 有 Context/Container 图
- [ ] 重大决策有 ADR 或内嵌 ADR 小节
- [ ] 未违反 FRAMEWORK-FREEZE

---

## 参考文件

- `business/skills/system-architecture-methodology/references/adr-template.md`
- `docs/ARCHITECTURE.md` · `docs/ARCHITECTURE-PORTS.md`
- `docs/FRAMEWORK-FREEZE.md`
