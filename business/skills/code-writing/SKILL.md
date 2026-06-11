---
name: code-writing
task_type: code-writing
description: 在 myteam 仓库内做最小正确实现，附带测试。
---

# code-writing — myteam 工程改动

配置贯通类任务 **先读**：`business/skills/myteam-config-linkage/SKILL.md`

改动 `frontend/` 任意文件 **先读**：`business/skills/hub-ui-debug/SKILL.md`（含语法/重复 let 扫描与「加载中」排查）

## 执行步骤

1. 只实现上游方案中的 **P0/P1** 项；每条对应一个 focused 变更。
2. 改动前阅读相邻代码，匹配现有风格；**禁止**无关格式化或重命名。
3. 配置类改动须同时更新：**读取端 + 写入端（API/前端）+ 单测**。
4. **每次保存前**跑快速回归，exit 0 才可 submit：

```bash
bash business/skills/myteam-config-linkage/scripts/run_linkage_tests.sh
# 若改了 frontend/*.js，另跑：
bash business/skills/hub-ui-debug/scripts/check_frontend_js.sh
```

5. 交付物写清：改了哪些文件、每项配置如何验证。

## 范围（myteam 系统升级）

**后端**（`developer`）：`kernel_config.py`、`store/`、`hub/api/server.py`、`backend/common/tests/`

**前端**（`frontend`）：`settings.js`、`index.html`、`app.js`

前后端须共用 arch 输出的 **API 契约表**（见 `templates/api_contract_table.md`）。

## 红线

- 禁止修改 `Process` / `AgentPort` 调度语义（框架封板）。
- 禁止 `saveSettings` 写 `cfg.models`（模型由 `/api/backends` 管理）。
- 禁止提交 `business/workspaces/`、`config/*.json` 运行态。
- 禁止未跑 `run_linkage_tests.sh` 就宣称完成。
