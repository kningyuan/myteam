---
name: xhs-operations
description: 小红书运营 workflow 共享包 — 选题调研 → 笔记成稿 → 真实发布留痕。
workflows:
  - 小红书运营
---

# xhs-operations — 小红书账号运营共享 Skill

**适用 workflow**：`小红书运营`（发布步使用 `template_id: publish-xhs`）。

各 step 的 `task_type` Skill 会引用本包；执行前 **先读本文件**，再读对应 task_type 的 `SKILL.md`。

## 四步链路

```text
t-research  选题调研     → 热点/竞品/受众/话题标签（表格 + 来源 URL）
t-strategy  内容策略     → 排期、标签策略、笔记形式
t-content   笔记成稿     → 标题 + 正文 + 标签 + 配图说明
t-publish   小红书发布   → 真实发文 + URL 截图（Gate 校验 xiaohongshu.com）
```

## 账号与登录（发布前必做）

Cookie 默认路径：`~/.gstack/xhs-cookies.json`（由 gstack browse 导出，与知乎共用 browse 二进制）。

```bash
# 1) 未登录或 cookie 过期：有头模式登录并导出 cookie
bash business/skills/xhs-operations/scripts/login_xhs.sh

# 2) 发布前只验登录态（不发文）
bash business/skills/xhs-operations/scripts/check_xhs_login.sh
```

退出码：`0` 已登录；`2` 未登录；`4` 人机验证。

## 必跑脚本（发布步）

在 **myteam 仓库根目录**执行：

| 步骤 | 脚本 |
|------|------|
| t-research | 填 `templates/topic_research_table.md` |
| t-content | 按 `templates/xhs_note_draft.md` 写交付物 |
| t-publish | `check_xhs_login.sh` → 发布（脚本或人工）→ `verify_publish_deliverable.py` |

```bash
# 静态校验（章节/URL/截图路径）
python3 business/skills/xhs-operations/scripts/verify_publish_deliverable.py \
  business/tasks/project/<project_id>/deliverables/t-publish_deliverable.md

# submit 前一步
bash business/skills/xhs-operations/scripts/run_publish_preflight.sh \
  business/tasks/project/<project_id>/deliverables/t-publish_deliverable.md
```

## 发布方式

**优先**：gstack browse 辅助（见 `publish-post/scripts/publish_xhs.sh`）  
**兜底**：人工在创作者中心发布，Agent 只提交真实 URL + 截图，**禁止伪造**。

小红书笔记通常需要至少 1 张配图；脚本无法自动上传图片时，须人工补图后由 Agent 截图回证。

## 红线

| 允许 | 禁止 |
|------|------|
| 公开信息调研 + 标注来源 URL | 编造阅读量、点赞数 |
| 真实发布 + 截图回证 | **伪造** `xiaohongshu.com` URL |
| 未登录/反爬失败如实上报 | 用草稿链接、预览链接冒充已发布 |
| 同一标题查重后再发 | 同一标题重复发布 |

## 与 task_type 的对应

| task_type | 读本包章节 + |
|-----------|-------------|
| research | 选题表模板；小红书受众/竞品/话题 |
| content | `xhs_note_draft.md` 笔记结构 |
| publish-post | 本文件 + `publish-post/SKILL.md` 小红书节 + `publish-xhs` 模板 |
