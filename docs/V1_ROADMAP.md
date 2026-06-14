# myteam v1 路线图（业务摘要）

> **版本**：2026-06-11  
> **执行门禁以 [V1_CAPABILITY_PLAN.md](./V1_CAPABILITY_PLAN.md) 为准**（Phase 0–4 + 总验收）。  
> 本文仅描述 **四条业务 workflow 的内容范围**，不含过关门禁命令。

---

## 业务 workflow 范围

| 优先级 | Workflow 文件 | MVP 任务链 |
|--------|---------------|------------|
| **P0** | `产品研发.yaml` | PRD → Gate → arch(按任务) → dev → qa → acceptance |
| **P1** | `媒体持续运营.yaml` | research → content → Gate → publish；`recurring` |
| **P2** | `产品经理交付.yaml` | product-planning → requirements → deck-build / wps-deck |
| **P3** | `GEO持续优化.yaml` | content → geo-audit → geo-plan → geo-verification |

**样板项目（已跑通）**：`产品规划方案` + TDS 第三章 — 见 `business/workflows/README.md`。

**arch 规则（Owner）**：大模块/新功能 = 方案 Gate + 实现 Gate；纯内容/小改动 YAML 内省略 arch。

**SEO/GEO**：发布前 GEO 优先；发布后 SEO/GEO 分 workflow；每月对齐会（见 FRAMEWORK_BOUNDARY §8.2）。

---

## 与能力计划的对应

| 路线图项 | 能力计划 Phase |
|----------|----------------|
| CI 全绿、discuss REG | Phase 0–1 |
| 四条 workflow YAML + REG | Phase 2 |
| recurring + 7 天试跑 | Phase 3 |
| Hub 校验、群消息入 DB、可选 PG | Phase 4 |
| Mac App API 契约 | Phase 4 |

---

## 不做（90 天）

见 [FRAMEWORK_BOUNDARY.md](./FRAMEWORK_BOUNDARY.md) §8.5。
