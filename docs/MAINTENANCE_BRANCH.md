# 维护分支说明 — `maint/slim-core`

> **用途**：专门维护 **Phase 1–2 瘦身之后** 的 myteam **工程代码**（内核、Hub、前端、模板、Skill 包、脚本、架构文档）。  
> **不维护**：各环境本地的 **运行配置与业务数据**（由 `.gitignore` 排除，部署时自行生成）。

---

## 分支定位

| 分支 | 角色 |
|------|------|
| **`maint/slim-core`** | 瘦身后工程主线：只收 **代码 + 模板 + 文档**，持续迭代 |
| `main` | 稳定发布线；验证通过后从 `maint/slim-core` 合并 |
| `feat/code-slimdown-p1` | 历史瘦身 PR 分支；基线已合入 `maint/slim-core` |

**创建基线**：`4adeb53` — Phase 1–2 code slimdown（移除 dead backend、frontend v1、orphan routes）。

---

## 维护范围（入库）

| 目录 | 内容 |
|------|------|
| `backend/` | 编排内核、Hub API、Adapter、Store |
| `frontend-v2/` | Web UI 源码（`dist/` 不入库） |
| `business/templates/` | Agent 名册、task_type 模板等 **静态模板** |
| `business/skills/` | Skill Pack（`SKILL.md`、方法论）；不含 `auto-*` 运行时草案 |
| `business/workflows/` | Workflow YAML **定义** |
| `business/delivery_templates/` | 交付物模板 |
| `scripts/` | bootstrap、回归、运维脚本 |
| `docs/` | 架构、手册、成熟度/QEL 等 **工程文档** |
| `config/` | 仅 **示例/结构**（若将来有 `*.example.json`）；**不含** `*.json` 运行配置 |

---

## 不维护（不入库，各环境本地）

已在 `.gitignore` 中排除，**本分支不跟踪、不 PR、不 review**：

| 路径 | 说明 |
|------|------|
| `config/*.json` | `system_config.json`、`skill_config.json` 等 |
| `business/config/` | `agents_config.json`、registry、groups、session_map |
| `business/workspaces/` | Agent 工作区与身份文件 |
| `business/tasks/` | `state.db`、项目交付物、运行事件 |
| `business/regression/artifacts/` | 回归取证大文件 |
| `venv/`、`.codegraph/`、`.claude/` | 本地工具与索引 |

克隆本分支后，需在本机执行 bootstrap（如 `scripts/bootstrap_business_roster.py`）并自行填写 `config/` 与 `business/config/`。

---

## 工作流

1. 从 `maint/slim-core` 拉功能分支：`feat/xxx`
2. PR 目标：**`maint/slim-core`**
3. 回归：`pytest`（相关子集）+ `frontend-v2` build
4. 稳定后：`maint/slim-core` → `main`

**禁止** 向本分支提交：`agents_config.json`、API Key、`.env`、sqlite 数据库、用户项目交付物。

---

## 与「配置不维护」的关系

- **工程配置结构**（代码里的默认值、`DEFAULT_CONFIG`、模板 JSON）→ **要维护**
- **运行实例配置**（端口、模型、Agent backend、名册实例化结果）→ **不维护**，各部署环境自己管

这样保证：**Git 上只有可复用的程序与模板；你的 Claude/opencode/Agent 配置不会进仓库，也不会被分支策略覆盖。**
