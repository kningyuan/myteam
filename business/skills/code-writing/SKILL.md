---
name: code-writing
task_type: code-writing
description: 在 myteam 仓库内做最小正确实现，附带测试。
---

# code-writing — myteam 工程改动

## 执行步骤

1. 只实现上游方案中的 **P0/P1** 项；每条对应一个 focused commit 粒度（可在一个交付物里分批说明）。
2. 改动前阅读相邻代码，匹配现有风格；**禁止**无关格式化或重命名。
3. 配置类改动须同时更新：**读取端 + 写入端（API/前端）+ 单测**。
4. 跑 `PYTHONPATH=backend pytest backend/common/tests/test_ui_config_linkage.py -q` 与相关模块测试。
5. 交付物写清：改了哪些文件、每项配置如何验证。

## 范围（myteam 系统升级）

**后端**（`developer`）：
- `backend/common/kernel_config.py` — process_defaults + executor 贯通
- `backend/hub/api/server.py` — 启动 kernel 读配置
- `backend/common/skill_settings.py` — 统一读取 helper
- `backend/common/tests/` — linkage 测试

**前端**（`frontend`，与后端分开任务，避免一人包办）：
- `frontend/settings.js` — loadSettings / saveSettings 与 API 字段对称
- `frontend/index.html` — 表单控件 id 与 settings.js 一致
- `frontend/app.js` — 新建项目默认值与 skill_config 对齐

前后端须共用 arch 输出的 **API 契约表**（`/api/config`、`/api/skill-config` 字段路径）。

## 红线

- 禁止修改 `Process` / `AgentPort` 调度语义（框架封板）。
- 禁止提交 `business/workspaces/`、`config/*.json` 运行态（gitignore）。
- 禁止 `--no-verify` 或跳过测试宣称完成。
