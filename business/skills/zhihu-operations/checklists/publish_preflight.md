# 知乎发布前清单（t-publish）

发布前逐项打勾；任一项未满足 **不得** 调用 `publish_zhihu.sh`。

## 内容与上游

- [ ] 已读 t-draft 交付物，`publish_title` 与正文最终版一致
- [ ] 标题无多余空格/全角符号导致 Gate 标题校验失败
- [ ] 正文 ≥800 字（或项目 goal 指定字数）
- [ ] 无未替换的占位符（`TODO`、`xxx`、`待补充`）

## 幂等（防重复发布）

- [ ] 项目 goal / 上游未提供「已发布 URL」——若已有 URL，**只补证据**勿二次发文
- [ ] 近 7 日未用同一标题发布过（查账号历史或上游记录）

## 环境与登录（发文前）

- [ ] `check_zhihu_login.sh` 退出码为 `0`
- [ ] 若为 `4`（人机验证）：已用 `login_zhihu.sh` 或 `browse connect` 人工通过
- [ ] `~/.gstack/zhihu-cookies.json` 存在且非空
- [ ] 正文过长时使用 `@<正文.md>` 传参
- [ ] `evidence/` 目录已创建

## 脚本与证据（发文后写交付物，submit 前校验）

- [ ] 已执行 `publish_zhihu.sh`，输出 URL 已写入交付物
- [ ] 按 `templates/publish_record.md` 填写各章节
- [ ] `verify_publish_deliverable.py` 退出码 `0`（或 `run_publish_preflight.sh`）
