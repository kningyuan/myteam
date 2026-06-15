---
name: "产品专家共享包"
description: 产品专家共享包 — PRD、策略、验收、演示文稿；协作与独立交付。
workflows:
  - 产品独立交付
  - 方案编制
  - 系统研发
  - 数据分析
agents:
  - product
---
# product-operations — 产品专家共享 Skill

**适用 agent**：`product`（产品专家）  
**适用 workflow**：`产品独立交付`、`方案编制`、`系统研发`、`数据分析` 等含 product 步骤的流程。

**必须先读**：`business/skills/product-methodology/SKILL.md`  
执行任意 product 相关 `task_type` 前 **再读本文件**，最后读对应 task_type 的 `SKILL.md`。

## 模式选择

| 模式 | 判断 | 读 |
|------|------|-----|
| **独立交付** | workflow=`产品独立交付` 或 goal 含「一人/独立」 | `playbooks/solo_delivery.md` |
| **协作** | 多 agent workflow | `playbooks/team_handoff.md` |

## task_type 路由

| task_type | 做什么 | 模板 / 脚本 / 路由 |
|-----------|--------|-------------------|
| `research` | 产品向桌面调研 | `templates/topic_research_table.md` |
| `product-research` | 产品调研（light_v1） | → `business/skills/product-research/SKILL.md` |
| `requirements` | PRD / 范围 / 验收 | `templates/prd_outline.md` |
| `strategy` | 策略方案 | `templates/strategy_memo.md` |
| `product-planning` | 产品整体规划章节 | → `business/skills/product-planning/SKILL.md` |
| `section-authoring` | 方案/文档章节编制 | → `business/skills/section-authoring/SKILL.md` |
| `section-review` | 章节内容质量审计（产品向） | → `business/skills/section-review/SKILL.md` |
| `deck-build` | 演示文稿 `.pptx` | `templates/deck_brief.yaml` → 见下方 |
| `acceptance-report` | 验收结论 | `templates/acceptance_checklist.md` |
| `decision-record` | 独立项目决策备忘 | `templates/decision_memo.md` |

## 演示文稿（deck-build）双路径

在 **myteam 仓库根目录**：

```bash
# 统一入口：优先 WPS（模板/图表），失败则 python-pptx 兜底
bash business/skills/product-operations/scripts/build_deck.sh \
  business/skills/product-operations/fixtures/sample_deck_brief.yaml \
  /path/to/deliverable/dir/deck.pptx

# 验收（Gate 前必跑）
python3 business/skills/product-operations/scripts/verify_deck.py \
  /path/to/deliverable/dir/deck.pptx \
  --deliverable /path/to/t-deck_deliverable.md
```

WPS 路径详情：`business/skills/wps-deck/SKILL.md`  
Preflight：`checklists/deck_preflight.md`

## PRD / 策略 Preflight

- PRD：`checklists/prd_preflight.md`
- 策略：交付物须含「不确定性」一词（Gate）

## 红线

- 禁止无验收标准（R1/R2…）的 PRD。
- 禁止 strategy 空泛复述上游，须引用具体结论。
- 禁止 deck-build 无 `deck.pptx` 文件仅写 Markdown 冒充交付。
- 禁止未跑 `verify_deck.py`（deck 步）或跳过 checklist 宣称完成。
- 独立模式 product **可兼** `decision-record`；协作模式交给 `main`。

##  smoke 测试（改 Skill 后）

```bash
bash business/skills/product-operations/scripts/run_skill_smoke.sh
```
