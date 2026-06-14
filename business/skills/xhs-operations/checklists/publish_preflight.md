# 小红书发布前清单（t-publish）

## 登录与账号

- [ ] 已运行 `check_xhs_login.sh`（exit 0）或已完成 `login_xhs.sh`
- [ ] `~/.gstack/xhs-cookies.json` 存在且非空（若使用 browse 脚本）
- [ ] 若为 `4`（人机验证）：有头 `browse connect` 人工通过后重试

## 内容与合规

- [ ] 标题、正文、标签与 t-content 一致（允许微调排版）
- [ ] 至少 1 张配图已准备（脚本无法上传时人工发布）
- [ ] 未使用未授权素材

## 交付物

- [ ] 按 `templates/publish_record.md` 填写四节 + 话题标签
- [ ] `已发布URL` 含 `xiaohongshu.com` 且为笔记详情页
- [ ] `证据截图` 路径相对交付物目录且文件存在
- [ ] 已运行 `verify_publish_deliverable.py` 通过

## 禁止

- [ ] 未伪造 URL 或截图
- [ ] 未用草稿/预览链接冒充已发布
