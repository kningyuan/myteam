---
name: content
task_type: content
description: 内容成稿 — 按平台规范输出可发布的标题与正文。
---

# content — 内容成稿

## 按 workflow 选共享包

| workflow | 先读 |
|----------|------|
| `知乎运营`、`内容运营`（知乎专栏） | `business/skills/zhihu-operations/SKILL.md` |

---

## 知乎专栏成稿（t-draft）

1. **输入**：读 t-research 交付物中的推荐选题、标题方向、关键词表。
2. **模板**：`business/skills/zhihu-operations/templates/zhihu_article_draft.md`
3. **结构要求**（Gate `content` task_type）：
   - 章节：`目标读者` `内容结构` `正文内容` `引用来源`
   - 正文须含 **关键词研究**、**目标读者** 字样（`must_include`）
   - 建议 **800 字以上**（以项目 goal 为准）
4. **GEO**：主关键词出现在标题 + 首段 + 一个小标题；长尾词自然分布，忌堆砌。
5. **为 t-publish 预留**：文末 YAML 块填写 `publish_title`；长文另存 `article_body.md`，发布时用 `@article_body.md`。

### 知乎文体要点

| 要素 | 建议 |
|------|------|
| 开篇 | 3 行内点明读者收益或反常识观点 |
| 段落 | 3–5 行/段，多用小标题与列表 |
| 论据 | 案例/数据须对应「引用来源」表 |
| 结尾 | 总结 + 可执行建议（非硬广） |

## 红线

- 禁止占位符提交（`TODO`、`<待填>`）。
- 禁止与 t-research 结论明显矛盾的标题/论点。
- 禁止抄袭；引用须进「引用来源」表。
