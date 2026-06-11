---
name: product-planning
task_type: product-planning
description: 产品说明/方案文档中的「产品整体规划」章节撰写与完善
agents:
  - product
---

# product-planning — 产品整体规划章节

**先读**：`business/skills/product-operations/SKILL.md`

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
4. **优势分析**：必须写 — 结合 2.5 竞品（浪潮、蚂蚁密算、安恒、零数）与四大组件差异化。
5. **功能架构**：文字描述模块关系；图位写「【图：功能架构图 — 见设计稿占位】」+ 图注说明。
6. **Verify**：`verify.log` 逐节自检；文末「与原文差异说明」列主要改动。
7. **交卷**：编辑 `deliverable` Markdown，**不要**直接改 docx；用户将 Markdown 粘贴回 Word。

## 红线

- 禁止与第一章组件定义（连接器/运营平台/合规监测/开发平台）矛盾。
- 禁止删除三期研发规划已有工期节点，只可细化范围与验收标准。
- 禁止空占位（「不写」「图」「解决了xxx」类句子不得原样留存在 deliverable）。
