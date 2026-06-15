---
name: "内容发布"
task_type: publish-post
description: 动作型任务——真实发布内容到外部平台并产出动作证据（已发布URL+截图），而非纸面方案。
---
# publish-post — 真实发布执行

本技能用于 `task_type: publish-post` 的**动作型任务**。交付物是 **动作证据**：线上 URL + 截图；Gate 会 **HTTP 访问 URL** 并核对标题。

## 知乎专栏（默认）

**先读**：`business/skills/zhihu-operations/SKILL.md`  
**发布前清单**：`business/skills/zhihu-operations/checklists/publish_preflight.md`

## 执行步骤

1. 从 t-draft 取 **最终标题** 与 **正文**（读 `publish_title` / 正文章节或 `article_body.md`）。
2. 若上游已有 `zhuanlan.zhihu.com/p/` URL → **只补截图与交付物**，勿重复发文。
3. 发布前 preflight（登录 + 交付物格式可先写草稿再校验）：

```bash
bash business/skills/zhihu-operations/scripts/check_zhihu_login.sh
# 未登录: bash business/skills/zhihu-operations/scripts/login_zhihu.sh
```

4. 调用发布脚本：

```bash
DELIV_DIR="<交付物目录>"
mkdir -p "$DELIV_DIR/evidence"
SHOT="$DELIV_DIR/evidence/zhihu-$(date +%Y%m%d-%H%M%S).png"
bash business/skills/publish-post/scripts/publish_zhihu.sh "标题" @article_body.md "$SHOT"
# 短文也可: ... "标题" "正文" "$SHOT"
```

5. 读取输出 `PUBLISHED_URL=`、`SCREENSHOT=`：
   - `0`：成功（URL 含 `zhuanlan.zhihu.com/p/`）
   - `2`：未登录 → `login_zhihu.sh` 后重试，**勿伪造 URL**
   - `3`：URL 异常 → 排查后重试
   - `4`：人机验证 → 有头登录后重试

6. 按模板写交付物：`business/skills/zhihu-operations/templates/publish_record.md`

7. submit 前静态校验：

```bash
python3 business/skills/zhihu-operations/scripts/verify_publish_deliverable.py \
  "<交付物目录>/t-publish_deliverable.md"
```

或一步：`bash business/skills/zhihu-operations/scripts/run_publish_preflight.sh <交付物.md>`

## 红线

- **绝不编造** URL 或截图；门禁会真实访问 URL。
- 截图路径写 **相对交付物目录**，文件须存在。
- 失败如实上报，由 Deputy/Main 安排重试，不得短路。

## 小红书笔记

**先读**：`business/skills/xhs-operations/SKILL.md`  
**Gate 模板**：workflow 任务 `template_id: publish-xhs`  
**发布前清单**：`business/skills/xhs-operations/checklists/publish_preflight.md`

```bash
bash business/skills/xhs-operations/scripts/check_xhs_login.sh
# 未登录: bash business/skills/xhs-operations/scripts/login_xhs.sh

DELIV_DIR="<交付物目录>"
mkdir -p "$DELIV_DIR/evidence"
SHOT="$DELIV_DIR/evidence/xhs-$(date +%Y%m%d-%H%M%S).png"
bash business/skills/publish-post/scripts/publish_xhs.sh "标题" @note_body.md "$SHOT"
# 笔记须配图：脚本无法上传时人工发布，再填真实 URL + 截图

python3 business/skills/xhs-operations/scripts/verify_publish_deliverable.py \
  "<交付物目录>/t-publish_deliverable.md"
```

## 其它平台

其它平台见对应 workflow；无专用脚本时须人工发布 + 真实 URL 证据。
