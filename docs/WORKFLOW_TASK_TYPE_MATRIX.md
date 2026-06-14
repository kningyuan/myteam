# Workflow × task_type 覆盖矩阵（Q-0）

> 2026-06-10 · 与 `business/skills/catalog.yaml` 同步

| workflow | task_id 示例 | task_type | Skill / 路由 | delivery_template |
|----------|--------------|-----------|---------------|-------------------|
| 产品规划方案 | ch3_quality_round-r*-work | product-planning | product-planning | tds-ch3-product-planning |
| 第三章-讨论链路测试 | discuss_test_round-r*-work | product-planning | product-planning | （同左） |
| 产品经理交付 | t-plan | product-planning | product-planning | — |
| 产品经理交付 | t-req | requirements | requirements | **prd-lite** |
| 产品经理交付 | t-deck | deck-build | deck-build / wps-deck | — |
| 小红书运营 | t-publish | publish-post | xhs-operations | publish-xhs |
| 媒体持续运营 | t-publish | publish-post | zhihu-operations | — |
| 产品研发 / myteam-platform-v3 / myteam-architecture-v4 | * | architecture-review, code-deliverable, code-review, code-testing, code-writing, test-plan | 对应 SKILL | — |
| GEO优化 / GEO持续优化 | * | geo-plan, geo-audit, geo-verification | geo-kernel（registry） | — |
| 数据分析 | * | data-analysis | data-analysis-kernel | — |
| 内容运营 | * | content, research, strategy | content / research | — |
| **self-upgrade** | upgrade-plan…release-decision | requirements, architecture-review, decision-record, code-writing, research, code-review, acceptance-report | product-operations / 各 router | — |
| （registry 示例） | — | code-deployment | registry 直驱 | — |
| （registry 示例） | — | deploy-run | registry 直驱 | **deploy-smoke** |
| （registry 示例） | — | config-bundle | config-bundle | **config-bundle** |

**内核直驱（无独立 Skill 目录）**：`geo-*`、`data-analysis` 由 `templates.yaml` + Gate 判定。

**验收**：每个 workflow 任务行的 `task_type` 在 catalog 有条目或上表标注「registry 直驱」。
