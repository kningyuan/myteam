---
name: publish-post
task_type: publish-post
description: 动作型任务——真实发布内容到外部平台并产出动作证据（已发布URL+截图），而非纸面方案。
---

# publish-post —— 真实发布执行

本技能用于 `task_type: publish-post` 的**动作型任务**。与「写方案/写草稿」不同，
本任务的交付物是**动作证据**：线上可访问的已发布 URL + 发布成功截图。
质量门禁会**真实访问**该 URL 并核对页面是否含帖子标题，证明动作确实发生。

## 执行步骤

1. 准备内容：根据任务描述确定 `标题` 与 `正文`（正文做好 GEO 关键词布局）。
2. 调用发布脚本（知乎专栏）：

```bash
SHOT="<交付物目录>/evidence/zhihu-$(date +%Y%m%d-%H%M%S).png"
bash ~/.openclaw/skills/team-ok/publish-post/scripts/publish_zhihu.sh "标题" "正文" "$SHOT"
```

3. 读取脚本输出的 `PUBLISHED_URL=` 与 `SCREENSHOT=`。
   - 退出码 `0`：发布成功（URL 形如 `zhuanlan.zhihu.com/p/<id>`）。
   - 退出码 `2`：未登录——需先 `$B connect` 手动登录知乎再重试，不要伪造 URL。
   - 退出码 `3`：发布后 URL 非文章页，疑似失败——排查后重试，**不得**编造已发布链接。

4. 按下面结构写交付物（章节标题必须与模板一致，门禁据此校验）：

```markdown
# 知乎发布记录

## 发布平台
知乎专栏（zhuanlan.zhihu.com）

## 帖子标题
<与线上页面完全一致的标题>

## 已发布URL
<脚本返回的 PUBLISHED_URL，单独成行>

## 证据截图
evidence/zhihu-YYYYMMDD-HHMMSS.png

## 正文摘要
<关键词布局与要点说明>
```

## 红线（务必遵守）

- **绝不编造已发布 URL 或截图**。门禁会真实访问 URL 核对标题，造假必被判失败。
- 截图路径写**相对交付物目录**的路径，且文件须真实存在（门禁 `file_exists` 会查）。
- 未登录/发布失败时如实上报失败原因，由上游（Deputy/Main）安排重试，不得短路。
