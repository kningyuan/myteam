# myteam 升级文档索引 — 2026-06-08

本目录按**天**归档 myteam 工业级协作框架升级的方案、共识与执行追踪。

## 文档清单

| 文件 | 内容 | 负责角色 |
|------|------|---------|
| [00-升级总路线图.md](./00-升级总路线图.md) | L1/L2/L3 三层演进、KPI 门禁、需求满足度 | 主控汇总 |
| [01-架构演进分析.md](./01-架构演进分析.md) | 差距矩阵、里程碑、架构风险 | 架构师 |
| [02-产品能力分析.md](./02-产品能力分析.md) | 三场景拆解、Cursor 对照、验证项目 | 产品主控 |
| [03-QA度量与回归体系.md](./03-QA度量与回归体系.md) | 8 KPI、REG-01~05、P0/P1 验收 | QA |
| [04-P0实施清单.md](./04-P0实施清单.md) | S1~S6 改动点、验收命令 | 开发 |
| [05-交叉讨论共识.md](./05-交叉讨论共识.md) | 四路 subagent 共识与分歧裁决 | 全员 |
| [06-Sprint0-执行追踪.md](./06-Sprint0-执行追踪.md) | Sprint 0 执行与评审 | 主控 |
| [07-Subagent协作治理规范.md](./07-Subagent协作治理规范.md) | 四阶段流程、开工/完工门禁 | 主控 |
| [08-Sprint1-需求对齐纪要-已签字.md](./08-Sprint1-需求对齐纪要-已签字.md) | Sprint 1 Phase 0 已签字范围 | 四路 |
| [09-Sprint1-功能预期对齐.md](./09-Sprint1-功能预期对齐.md) | Sprint 1 Phase 3 完工门禁（**L1_GATE_PASS**） | 主控 |
| [10-Sprint1-REG执行记录.md](./10-Sprint1-REG执行记录.md) | REG-02/04/05 执行与 KPI（均已 PASS） | 主控 |
| [11-Sprint1-交叉验证纪要.md](./11-Sprint1-交叉验证纪要.md) | 四路交叉验证 + REG-02 闭环（迭代 3） | 主控 |
| [12-L2-交叉验证纪要.md](./12-L2-交叉验证纪要.md) | L2 四路交叉验证 + 并行/K8/fail_reason 验收（**L2_GATE_PASS**） | 主控 |
| [13-L3-需求对齐纪要.md](./13-L3-需求对齐纪要.md) | L3 自进化 Phase 0 对齐 + scaffold 范围（**L3_SCAFFOLD**） | 主控 |
| [14-L2-框架封板门禁.md](./14-L2-框架封板门禁.md) | **L2_FRAMEWORK_SEAL** 封板清单与验收命令 | 主控 |
| [15-标准协作模式总结.md](./15-标准协作模式总结.md) | **金路径配方**、E2E 验证、是否还需改内核 | 主控 |
| [../new/03-需求-实现映射与演进.md](../new/03-需求-实现映射与演进.md) | 需求 ID ↔ 代码锚点（**实现真相源**） | 主控 |

## 上游输入

- 交接：`/tmp/myteam-handoff-20260610-session10.md`（L2 闭环 + L3 scaffold）
- 分支：`upgrade/continued`

## 当前架构速查（2026-06-10 后）

- 总览：[docs/ARCHITECTURE.md](../ARCHITECTURE.md)
- 文档索引：[docs/README.md](../README.md)
- Agent 名册：`business/templates/business-roster.json`（`research` 非 `researcher`）

## 治理约定

1. **一层一 Sprint**：L1 未完成不开 L2 新功能
2. **每项改动绑定 KPI + pytest/REG**
3. **四路评审**：开发实施 → QA 验收 → 架构 invariant 检查 → 产品目标对齐
4. **文档随日更新**：当日决策与状态写入本目录
