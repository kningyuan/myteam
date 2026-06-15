---
name: "调研"
task_type: research
description: 调研与全景盘点 — 输出可验证的来源表与结构化发现。
---
# research — 调研

## 按 workflow 选共享包

| workflow / 任务 | 先读 |
|-----------------|------|
| `产品独立交付`、`方案编制`（product 步骤） | `business/skills/product-operations/SKILL.md` |
| `myteam系统升级`、配置贯通 | `business/skills/myteam-config-linkage/SKILL.md` |
| `知乎运营`、`内容运营`（知乎） | `business/skills/zhihu-operations/SKILL.md` |

---

## 产品向调研（产品独立交付 · t-brief / product research）

1. 从【项目目标】提取：用户、场景、商业目标。
2. 骨架：`business/skills/product-operations/templates/topic_research_table.md`
3. **关键发现**须含表格：用户与场景、竞品、机会与约束。
4. **结论**给出推荐方向与不建议项。

## 知乎选题调研（知乎运营 · t-research）

1. 从【项目目标】提取：账号领域、选题方向、禁忌。
2. 用 `business/skills/zhihu-operations/templates/topic_research_table.md` 作为交付物骨架。
3. **关键发现**须含三张表：受众定位、竞品选题、关键词/GEO（见模板）。
4. **结论**给出：推荐选题、2–3 个标题方向、成稿要点（供 t-draft）。
5. 每条数据标注 **来源 URL**；禁止编造阅读量/粉丝数。

## 配置盘点（myteam系统升级 · t-inventory）

1. 运行：

```bash
bash business/skills/myteam-config-linkage/scripts/scan_config_inventory.sh
```

2. 用 `templates/field_matrix.md` 填 UI id ↔ JSON path ↔ 后端读取点。
3. 对「是否生效」追到 `kernel_config.py`、`skill_settings.py`、Hub 启动路径。

交付物章节：`调研背景` `信息来源` `关键发现`（含表格）`结论`。

## self-upgrade · skill-extract（REG-L3）

当 workflow 为 `self-upgrade` 且 task_id 为 `skill-extract`：

1. 阅读 `docs/DESIGN-SKILL-SYSTEM.md` 与 `impl-upgrade` 交付物。
2. 输出 **research** 交付物：总结可写入正式 Skill 的 3–5 条模式（步骤/红线/脚本）。
3. 填写 `ledger.entry.yaml` 的 `lesson.next_time`，供 L4 人工合入。
4. 项目 **completed** 后，内核会在 `business/skills/auto-self-upgrade-skill-extract/SKILL.md` 写 L3 草案（勿与本文混淆）。

## 通用红线

- 禁止无来源的数据结论。
- 禁止在调研步改代码（配置盘点步）。
- 关键发现须用 **表格** 呈现（Gate 友好）。
