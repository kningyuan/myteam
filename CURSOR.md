# Using this repo with Cursor

本仓库已配置 **Karpathy 行为准则** Cursor 规则，在 Cursor 中打开 `myteam` 目录即可自动生效。

## 在本仓库

1. 用 Cursor 打开 `myteam` 文件夹。
2. 规则 [`.cursor/rules/karpathy-guidelines.mdc`](.cursor/rules/karpathy-guidelines.mdc) 已提交，`alwaysApply: true`，无需额外安装。
3. 可在 **Settings → Rules** 中确认 `karpathy-guidelines` 已加载。

## 来源

基于 [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) 的 CURSOR.md 说明；准则内容与 upstream 的 `CLAUDE.md` / `.cursor/rules/karpathy-guidelines.mdc` 保持一致。

## myteam 项目约定（补充）

- 路径唯一来源：`backend/hub/paths.py`（Hub）、`skill/team/common/paths.py`（协作 skill）
- Agent 注册表：`config/agents_registry.json`（Main 选团队时读取）
- 系统配置：`config/system_config.json`；协作引擎配置：`config/skill_config.json`
- 项目进度通报：myteam 项目群（team_config 后自动创建），**不使用 Telegram**
