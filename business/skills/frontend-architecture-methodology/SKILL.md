---
name: frontend-architecture-methodology
task_type: frontend-architecture-methodology
description: >-
  前端架构方法论：信息架构→组件边界→状态与数据流→性能与可访问性→trade-off。
  frontend 执行 system-design / architecture-review 时必须与本 skill 及 system-architecture-methodology 联读。
---

# 前端架构方法论（myteam 适配版）

> **来源合成**（已裁剪）：
> - 组件化 / 容器-展示分离
> - 前端架构决策记录（轻量 ADR）
> - API 契约消费与 Port 模式（对齐 myteam frontend-v2）
> - Core Web Vitals / 性能预算思路

**myteam 红线**：读 `docs/FRAMEWORK-FREEZE.md`；Hub API 契约以 arch 输出为准；禁止建议重写内核调度。

---

## 何时启用

- `agent_id=frontend` 且 `task_type` 为 system-design 或 architecture-review
- 前端模块拆分、状态管理选型、与 Hub API 边界设计

---

## 执行流程（必须按序）

### Step 1 — 前端问题与约束

| 维度 | 内容 |
|------|------|
| 用户任务 | 用户要完成什么（非页面列表） |
| 运行环境 | 浏览器、Hub 内嵌、SSR/CSR |
| 硬约束 | 现有 stack（如 React/Vite）、API 已存在端点 |
| 非目标 | 不做全站 redesign、不新增后端 API（除非 workflow 要求） |

### Step 2 — 信息架构与路由

- 页面/视图清单与 **导航关系**（可 Mermaid 或列表）
- 每个视图：**输入数据 | 用户操作 | 输出/副作用**

### Step 3 — 组件边界

分层建议（按项目选用，须写 trade-off）：

| 层 | 职责 | myteam 示例 |
|----|------|-------------|
| Page | 路由级编排 | Manage 页 |
| Feature | 业务块 | Workflow 编辑器 |
| UI | 无业务纯展示 | Button, Table |
| lib/ports | API 抽象 | ChatPort, ProjectsPort |

**禁止** Page 直接 fetch 散落各处 — 须经 port 或 api 模块。

### Step 4 — 状态与数据流

写清：

- **Server state**（API 拉取） vs **Client state**（UI 局部）
- 缓存/刷新策略（何时 invalidate）
- 错误与 loading 的统一模式

输出 **数据流图** 或逐步说明：User action → Port → Hub API → UI update。

### Step 5 — 与后端契约对齐

- 引用 arch 的 **API 契约表**（method, path, request/response 字段）
- 标注 frontend owner 的字段与校验规则
- 发现契约缺口 → 记入「演进建议」，**不擅自扩 API**

### Step 6 — 质量属性与 trade-off

选 3 项排序：可维护性、性能、可测试性、可访问性、a11y、DX。

```markdown
| 选项 | 满足 | 牺牲 | 复杂度 | 推荐场景 |
|------|------|------|--------|----------|
| 集中 api 模块 | … | … | 低 | myteam 默认 |
| … | … | … | … | … |
```

**选定方案** + 不选其他的首要理由。

### Step 7 — 前端架构 ADR（可选但推荐）

重大选型（状态库、路由、构建）写 5 段 ADR：Context / Decision / Options / Consequences / Status。

---

## 与 system-architecture-methodology 的分工

| 本 skill | system-architecture-methodology |
|----------|--------------------------------|
| UI 边界、组件、数据流 | 系统 Context/Container、内核 Ports |
| Hub 消费契约 | Store/Process/Adapter 全栈边界 |
| 前端 performance/a11y | 后端模块化、ADR 全栈 |

两者 **都读**，交付物按 task_type 模板章节合并，避免重复粘贴。

---

## 反模式（禁止）

- 未读 `frontend-v2/ARCHITECTURE.md` 就提议全新目录结构
- 在 architecture-review 中直接改 backend 代码（frontend 专责 t-fe-contract 只读 frontend）
- 无 trade-off 的单方案「推荐 React Query」类断言
