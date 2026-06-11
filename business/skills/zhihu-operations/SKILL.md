---
name: zhihu-operations
description: 知乎运营 workflow 共享包 — 选题调研 → 专栏成稿 → 真实发布留痕。
workflows:
  - 知乎运营
  - 内容运营
---

# zhihu-operations — 知乎账号运营共享 Skill

**适用 workflow**：`知乎运营`、`内容运营`（发布步为知乎专栏时）。

各 step 的 `task_type` Skill 会引用本包；执行前 **先读本文件**，再读对应 task_type 的 `SKILL.md`。

## 三步链路

```text
t-research  选题调研     → 竞品/关键词/受众（表格 + 来源 URL）
t-draft     知乎成稿     → 标题 + 正文 + GEO 关键词（须过字数与结构）
t-publish   知乎发布     → 脚本真实发文 + URL 截图（Gate 会 HTTP 验标题）
```

## 账号与登录（发布前必做）

Cookie 默认路径：`~/.gstack/zhihu-cookies.json`（由 gstack browse 导出）。

```bash
# 1) 未登录或 cookie 过期：有头模式登录并导出 cookie
bash business/skills/zhihu-operations/scripts/login_zhihu.sh

# 2) 发布前只验登录态（不发文）
bash business/skills/zhihu-operations/scripts/check_zhihu_login.sh
```

退出码：`0` 已登录；`2` 未登录；`4` 人机验证（需有头 `browse connect` 人工通过后重试）。

## 必跑脚本（按步骤）

在 **myteam 仓库根目录**执行：

| 步骤 | 脚本 |
|------|------|
| t-research | 填 `templates/topic_research_table.md` |
| t-draft | 按 `templates/zhihu_article_draft.md` 写交付物 |
| t-publish | 发布前 `check_zhihu_login.sh` → `publish_zhihu.sh` → 写交付物 → submit 前 `verify_publish_deliverable.py` |

```bash
# 发布交付物静态校验（章节/URL/截图路径，不访问外网）
python3 business/skills/zhihu-operations/scripts/verify_publish_deliverable.py \
  business/tasks/project/<project_id>/deliverables/<task_id>_deliverable.md

# 发布前：登录态（发文前）
bash business/skills/zhihu-operations/scripts/check_zhihu_login.sh

# submit 前：交付物 + 登录（交付物写好后）
bash business/skills/zhihu-operations/scripts/run_publish_preflight.sh \
  business/tasks/project/<project_id>/deliverables/t-publish_deliverable.md
```

## 模板与清单

- 选题表：`templates/topic_research_table.md`
- 成稿结构：`templates/zhihu_article_draft.md`
- 发布记录：`templates/publish_record.md`
- 发布前清单：`checklists/publish_preflight.md`

## 红线

| 允许 | 禁止 |
|------|------|
| 公开信息调研 + 标注来源 URL | 编造阅读量、粉丝数、竞品数据 |
| 真实脚本发布 + 截图回证 | **伪造** `zhuanlan.zhihu.com/p/` URL |
| 未登录/反爬失败如实上报 | 用草稿链接、预览链接冒充已发布 |
| 重试前查 `checklists/publish_preflight.md` | 同一标题重复发布（须先查是否已发） |

## 与 task_type 的对应

| task_type | 读本包章节 + |
|-----------|-------------|
| research | 选题表模板；知乎受众/竞品/关键词 |
| content | 成稿模板；800 字+、H2 结构、GEO 关键词 |
| publish-post | 发布脚本 + 发布记录模板 + preflight |
