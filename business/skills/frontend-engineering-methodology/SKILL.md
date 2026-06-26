---
name: 前端工程方法论
description: 前端实现方法论：最小 diff、契约对齐、组件实现、自测与回归。
---
# 前端工程方法论（myteam 适配版）

> **来源合成**（已裁剪）：
> - 实现前读相邻代码、匹配现有风格
> - 组件测试 / 手验清单
> - Hub UI 调试与 JS 静态扫描（myteam 专项）

**myteam 红线**：改 `frontend/` 须读 `hub-ui-debug` skill；禁止改 Process/AgentPort；禁止未跑回归就 submit。

---

## 何时启用

- `agent_id=frontend` 且 code-writing / code-deliverable / code-review
- Hub Manage UI、settings、workflow 编辑器相关实现

---

## 执行流程（必须按序）

### Step 1 — 对齐上游

1. 读 arch 交付物中的 **P0/P1 清单** 与 **API 契约表**
2. 只实现清单内项；每条变更对应一个 focused commit 级 diff
3. 确认 **读取端 + 写入端** 对称（load/save、GET/PUT 字段一致）

### Step 2 — 探索现有代码

- 打开将要修改的文件及 **调用方/被调用方**
- 命名、import 风格、错误处理方式与周边一致
- **禁止** 无关格式化、重命名、顺手重构

### Step 3 — 实现顺序

推荐顺序：

1. **lib/api 或 ports** — 类型与 HTTP 封装
2. **组件/页面** — 消费 port，不裸 fetch 散落
3. **样式** — 沿用现有 design tokens / class 惯例
4. **联调** — 对契约表逐项手验

### Step 4 — 自测（保存前必跑）

```bash
# frontend
cd frontend && npm run build

# 若改 legacy frontend/*.js
bash business/skills/hub-ui-debug/scripts/check_frontend_js.sh
```

配置贯通类另跑：

```bash
bash business/skills/myteam-config-linkage/scripts/run_linkage_tests.sh
```

exit 0 才可 submit；失败须写入 known_gaps，禁止隐瞒。

### Step 5 — 交付物说明

交付物或 PR 描述须含：

| 项 | 内容 |
|----|------|
| 变更文件 | 路径列表 |
| 对应 P0/P1 | 上游清单 id |
| 验证步骤 | 可复现的手动步骤 |
| 回归命令 | 实际执行的命令与结果 |

### Step 6 — Code Review 视角（code-review）

- 契约一致性 > 代码风格 > 微优化
- 标记：**阻塞 / 建议 / nit**
- 无跑通 build 的改动 → 阻塞

---

## 与 hub-ui-debug 的关系

改任意 `frontend/` JS：**必须先读** `business/skills/hub-ui-debug/SKILL.md`（重复 let、加载中、语法扫描）。

本方法论管 **流程**；hub-ui-debug 管 **Hub 专项排障**。

---

## 反模式（禁止）

- saveSettings 写 `cfg.models`（模型由 `/api/backends` 管理）
- 单文件巨型组件无边界
- 未 build 就宣称「UI 已完成」
- 提交 `business/workspaces/`、`config/*.json` 运行态
