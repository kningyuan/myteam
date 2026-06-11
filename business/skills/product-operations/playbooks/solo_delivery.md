# 产品独立交付 — 一人闭环

适用 workflow：`产品独立交付`

## 步骤顺序

```text
t-brief (research)     → 背景/竞品/约束（轻量，≤1500字）
t-req (requirements)   → PRD：范围 + 用户故事 + R1/R2 验收
t-strategy (strategy)  → 背景/分析/方案/建议
t-deck (deck-build)    → deck.pptx（10±2 页）
t-accept (acceptance)  → 对照 t-req 验收标准逐项 PASS/FAIL
t-decision (可选)      → 决策备忘（无 main 时 product 执行）
```

## 每步输入输出

| 步 | 输入 | 产出物 |
|----|------|--------|
| t-brief | 【项目目标】 | `t-brief_deliverable.md` |
| t-req | t-brief | `t-req_deliverable.md` |
| t-strategy | t-brief, t-req | `t-strategy_deliverable.md` |
| t-deck | t-strategy 结论 + `deck_brief.yaml` | `deck.pptx` + `t-deck_deliverable.md` |
| t-accept | t-req, t-deck | `t-accept_deliverable.md` |

## deck 内容来源

从 t-strategy 提取：标题、3–5 个核心论点、1 页风险/下一步。  
填 `deck_brief.yaml` 后跑 `build_deck.sh`，勿在 PPT 里重写长篇 PRD。

## 时间盒

- brief + req：各 1 轮 execute
- strategy + deck：各 1 轮；deck 失败先用 python 兜底，再排 WPS 环境
