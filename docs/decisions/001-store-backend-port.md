# ADR-001: Store 持久化采用 Ports + SQLite 默认实现

## Status

Accepted

## Date

2026-06-14

## Context

myteam 运行态真相在 SQLite（`business/tasks/state.db`），单用户本地部署，~12MB WAL。Platform v3/v4 要求消除 Hub/agent_port 直写 bypass，并为未来 PG 留接口。

**质量属性优先级**：1 可测试性 2 可演进性 3 运维简单 4 水平扩展（当前非目标）

## Options Considered

### Option A: 继续 Store 内嵌 SQLite，无抽象

- Pros: 最少代码、零迁移风险
- Cons: PG/多实例时大改；测试难注入 fake backend

### Option B: StoreBackend Protocol + SQLiteStoreBackend（Ports）

- Pros: 与 CLIAdapter 同模式；测试可 mock；PG 可后插
- Cons: 一层 indirection；需维护 Protocol 表面

### Option C: 立即切换 PostgreSQL

- Pros: 多实例、连接池成熟
- Cons: 单用户本地过重；无 PG CI；迁移成本高

## Decision

We choose **Option B** because:

1. 与既有 Hexagonal 方向（Adapter、TokenUsageSink）一致
2. 当前约束下 SQLite 足够，抽象成本可控
3. Gate 可用 pytest 验证 backend 注入，不依赖 PG 环境

## Consequences

- 正面：生产 bypass 归零；架构决策可审计
- 代价：Store 构造多一个参数；PG 实现仍为 backlog
- 重新评估触发：多 Hub 实例并发写 / state.db >100MB / 需跨机共享状态
