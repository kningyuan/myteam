---
name: section-authoring
task_type: section-authoring
description: 方案/说明文档指定章节的撰写与完善 — Gate 章节与 Goal 对齐
agents:
  - product
---

# section-authoring — 方案编制

**必须先读**：`business/skills/product-methodology/SKILL.md`  
**再读**：`business/skills/product-operations/SKILL.md`

## 输入

1. 【项目目标】Goal：文档对象、章节名/号、只读材料路径、是否配图等。
2. 上游交付物（如缺口分析、上一轮审计反馈）。

## 执行步骤

1. **章节对象**：在 deliverable 首章写清 Goal 指定的文档、章节范围、本轮 round（若循环内）。
2. **正文**：按 Goal 扩写/完善章节；Markdown H2 结构须与 `templates.yaml` → `section-authoring` 一致。
3. **依据与引用**：列材料路径与关键结论对齐说明；禁止未读材料即断言。
4. **变更说明**：相对源稿或上一轮 `section-review` 修订要求，列主要改动。
5. **自检清单**：逐条对照 Goal 与本 task_type 五章 Gate；未通过项不得交卷。
6. **交卷**：编辑 deliverable Markdown，供用户粘贴回源文档；勿直接改 Word/PDF 源文件。

## Gate 章节（H2 须逐字）

| 章节 | 要求 |
|------|------|
| 章节对象 | 文档名、章节、范围 |
| 正文 | 完整可粘贴正文 |
| 依据与引用 | 材料路径 + 对齐说明 |
| 变更说明 | 本轮相对上版改动 |
| 自检清单 | 逐条 PASS/FAIL 自检 |

## 红线

- 禁止空占位（「待补充」「TBD」「图」原样留存）。
- 禁止与 Goal 指定章节范围无关的扩写。
- 禁止跳过自检清单交卷。
