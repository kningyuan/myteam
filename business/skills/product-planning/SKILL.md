---
name: product-planning
task_type: product-planning
description: 产品说明/方案文档中的「产品整体规划」章节撰写与完善
agents:
  - product
---

# product-planning — 产品整体规划章节

**必须先读**：`business/skills/product-methodology/SKILL.md`  
**再读**：`business/skills/product-operations/SKILL.md`

## 输入材料（必读）

| 文件 | 用途 |
|------|------|
| `business/inputs/trusted-data-space/source_ch1_overview.md` | 第一章产品概述（勿改结论，须对齐） |
| `business/inputs/trusted-data-space/source_ch2_market.md` | 第二章市场与客户需求 |
| `business/inputs/trusted-data-space/source_ch3_current.md` | 第三章现状骨架与占位 |
| `business/inputs/trusted-data-space/副本可信数据空间.docx` | 原 Word 稿（可选对照） |

## 执行步骤

1. **Align**：在 `align.md` 写清本章对象、须保留的原稿表述、须补齐的占位（如「优势分析不写」「功能架构图」）。
2. **通读一二章**：四大组件、五类场景、济南/山东客户需求须在第三章方案中可追溯。
3. **扩写第三章**：按 `templates.yaml` 的 H2 章节撰写；保留原稿已合理的三期研发工期与范围，补全分析性段落。
4. **产品架构图**：须作图并交付 `product-architecture.drawio` + `product-architecture.png`，Markdown「### 产品架构」内嵌 `![](product-architecture.png)` 与图注。
5. **优势分析**：必须写 — 结合 2.5 竞品（浪潮、蚂蚁密算、安恒、零数）与四大组件差异化。
6. **功能架构**：文字描述四大组件功能域；须作图并交付 `functional-architecture.drawio` + `functional-architecture.png`，内嵌 `![](functional-architecture.png)` 与图注。
7. **Verify**：`verify.log` 逐节自检 + draw.io 探针/PNG 导出记录。
8. **交卷**：编辑 `deliverable` Markdown，**不要**直接改 docx；用户将 Markdown 粘贴回 Word。

## 第 2+ 轮 · PATCH 改稿（Work–Review 循环）

当轮次 > 1 且项目 meta 含「定点改稿清单」时：

1. **打开本轮初稿**：`deliverables/{work_task_id}_deliverable.md`（内核已从上一轮复制）。
2. **只改清单项**：逐条 PATCH 对应 ### 小节；未列出的章节 **一字不改**。
3. **verify.log** 追加 PATCH 记录：改了哪一节、改了什么、对应 review 哪一条。
4. **禁止**：全文重写、调换章节顺序、顺带「优化」未要求段落。
5. 群讨论全文见 `{loop_id}-r{prev_round}-group_discussion.md`。

## 红线

- 禁止与第一章组件定义（连接器/运营平台/合规监测/开发平台）矛盾。
- 禁止删除三期研发规划已有工期节点，只可细化范围与验收标准。
- 禁止空占位（「不写」「图」「解决了xxx」类句子不得原样留存在 deliverable）。
