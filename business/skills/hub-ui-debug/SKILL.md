---
name: "Hub UI 调试"
description: Hub 前端故障排查与修复 — 页面一直加载、init 崩溃、总览空白等。
workflows:
  - myteam系统升级
scenarios:
  - 首页总览刷新后一直「加载中」
  - 设置页按钮无反应
  - 切 Tab 后页面恢复
---
# hub-ui-debug — Hub 前端故障排查（共享 Skill）

**适用**：myteam `frontend/` 相关 bug 修复、`code-writing` / `acceptance-report` 中涉及 UI 的验收。

Agent **先读本文件**，再改 `app.js` / `settings.js` / `dashboard.js` 等。

## 典型症状 → 优先怀疑

| 症状 | 常见根因 |
|------|----------|
| 首页「总览」刷新后 **一直转圈**，切 Tab 再回来就好 | `init()` 在 `setupEventListeners()` **中途抛错**，`renderDashboard()` 从未执行 |
| Console 有 `ReferenceError: xxx is not defined` | 某 `<script>` **整文件未加载**（语法错 / 重复 `let` 全局变量） |
| `typeof saveSettings === 'undefined'` | `settings.js` 加载失败（见下方 2026-06 案例） |
| 仅 settings/管理 Tab 异常 | 同上，或 `manage.js` 依赖未定义 |

## 2026-06 已验证案例（首页总览）

**根因链**：

```text
project.js: let _sysCfg
settings.js: let _sysCfg   ← 重复声明，settings.js 整文件解析失败
→ saveSettings 不存在
→ init() → setupEventListeners() 抛 ReferenceError
→ ensureHomeDashboard() 未运行
→ #home-projects 永驻「加载中…」
```

**次要**：`saveSettings()` 内 `process_defaults` 对象括号不匹配（`node --check` 可抓）。

**修复原则**：

- 全局变量 **只在一处 `let` 声明**；其它文件只读写或注释说明共用。
- `init()` 关键路径：`restoreUiState` → `ensureHomeDashboard()`；总览 **不等待** `/api/backends`。
- 改 `frontend/*.js` 后 ** bump `index.html` 里 `?v=`**，避免浏览器旧缓存。

## 排查步骤（必做）

在 **myteam 仓库根目录**：

```bash
# 1) 全前端 JS 语法 + 重复 let 扫描
bash business/skills/hub-ui-debug/scripts/check_frontend_js.sh

# 2) API 探活（Hub 需已启动，默认 8765）
bash business/skills/hub-ui-debug/scripts/probe_hub_ui_api.sh
```

浏览器：**硬刷新** `Cmd+Shift+R` → DevTools Console **无红字** → Network 看 `/api/obs/summary` 是否 200。

按清单逐项打勾：`checklists/stuck_loading.md`

## 修复后验证

1. `check_frontend_js.sh` exit 0  
2. 硬刷新后首页总览 **≤3s** 出现项目卡片或空态引导（非「加载中」）  
3. localStorage `agentHub_uiState_v2` 为 `tab:home` 时，刷新仍正常  
4. 交付物用模板：`templates/fix_report.md`

## 关键文件地图

| 文件 | 职责 |
|------|------|
| `frontend/app.js` | `init()`、`switchTab`、`restoreUiState` |
| `frontend/dashboard.js` | `renderDashboard()`、`ensureHomeDashboard()` |
| `frontend/settings.js` | 设置页；**勿重复声明** `_sysCfg` |
| `frontend/project.js` | `_sysCfg` 声明处（与 settings 共用） |
| `frontend/index.html` | script 顺序与 `?v=` 缓存戳 |

## 红线

- 禁止未跑 `check_frontend_js.sh` 就宣称「UI 已修复」。
- 禁止在多个 frontend 文件重复 `let` 同名全局变量。
- 禁止只靠「切 Tab 能好」当作已修复（那是 bypass，不是根因修复）。
- 改 UI 时 **最小 diff**；不顺手重构无关 Tab。

## 与 task_type 的引用

| task_type | 何时读本包 |
|-----------|-----------|
| code-writing | 改动 `frontend/` 任意文件 |
| code-testing | 回归含 UI 手验或脚本 |
| acceptance-report | 验收含 Hub 页面 |
