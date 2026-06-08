# Agent 能力库（agent-catalog）

本目录是外部专业 agent 人格库的**只读镜像**，作为 myteam 激活专业 agent 时的**素材源**（人格 / 交付物模板 / 成功指标）。它本身不参与运行——运行态的 agent 在 `business/workspaces/` 与 `business/config/agents_registry.json`。

## 来源与许可
- 上游：[msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents)（约 218 agents / 15 divisions）
- 许可：**MIT**（可自由商用/个人使用，署名感谢但不强制）。本目录保留上游原文。
- 当前已 vendor：`product/product-manager.md`（样板，用于验证激活链路）

## 为什么是"只读镜像"
保持上游纯净以便日后 re-pull；myteam 的本地化与 task_type 适配产物写进 workspace 与 `templates.yaml`，**不回写本目录**。

## 如何激活一个 agent（选取 → 升级）
1. 从本库选一个 `<division>/<agent>.md`。
2. **指派 myteam task_type**——优先映射到已有的 `research / strategy / code-* / test-* / content / seo-plan`；确无现成契约时才新增，并在 `templates.yaml` 补 `deliverable_template` + `check_rules`。
3. 把人格 / 工作流 / 语气**改写**进目标 workspace 的 `SOUL.md / AGENTS.md / IDENTITY.md / CLAUDE.md`（中文化、套进 task_type 门禁、**裁掉越界能力**）。
4. `register_agent(..., task_types=[...])` 写注册表；在 `agents_config.json` 设 backend/model。

> ⚠️ **边界即安全线**：agency-agents 的 agent 往往覆盖比 myteam 角色更宽的职责（如 product-manager 含 PRD/sprint/GTM）。激活时**只取符合该角色 task_type 边界的部分**，不要让外部人格覆盖 myteam 的角色门禁。

## 已激活映射
| catalog 源 | → myteam agent | task_types | 升级说明 |
|---|---|---|---|
| `product/product-manager.md` | `product` | strategy, research | 取「问题优先 / 机会评估+RICE / Now-Next-Later / 置信度沟通 / 不做清单」；**裁掉** PRD·sprint·GTM·launch（越 strategy·research 边界） |
