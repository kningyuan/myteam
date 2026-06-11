# 页面一直「加载中」排查清单

## 浏览器（30 秒）

- [ ] 硬刷新 `Cmd+Shift+R`（非普通 F5）
- [ ] DevTools → Console：**无红色** ReferenceError / SyntaxError
- [ ] Network：`/api/obs/summary` 状态 200（首页总览）
- [ ] Network：`/static/settings.js` 状态 200 且非旧版本（对照 `index.html` 的 `?v=`）

## 脚本（仓库根目录）

- [ ] `bash business/skills/hub-ui-debug/scripts/check_frontend_js.sh` → exit 0
- [ ] Hub 已启动：`bash business/skills/hub-ui-debug/scripts/probe_hub_ui_api.sh` → exit 0

## 根因分类

- [ ] 某 JS 文件语法错误 → `node --check frontend/<file>.js`
- [ ] 跨文件 **行首** 重复 `let 同名变量` → 扫描脚本已报 duplicate
- [ ] `init()` 未跑完 → Console 第一条报错栈指向 `setupEventListeners` / `init`
- [ ] API 挂掉 → summary/config 非 200（后端问题，非纯前端）
- [ ] 仅 Tab 切换后恢复 → **init 崩溃** 高度可疑，不是「慢」

## 修复后

- [ ] 刷新后目标 Tab 正常，无需切 Tab 才恢复
- [ ] `index.html` 中改动过的 script 已 bump `?v=`
- [ ] 交付物含：根因一句话 + 改动文件 + 验证命令输出
