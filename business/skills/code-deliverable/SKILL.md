---
name: code-deliverable
task_type: code-deliverable
description: 代码工程交付 — deliverables/<task_id>/ 可运行脚本 + output/ + README。
---

# code-deliverable — 代码工程交付

**必须先读**（内核按 agent_id 注入）：
- `developer` → `business/skills/backend-engineering-methodology/SKILL.md`
- `frontend` → `business/skills/frontend-engineering-methodology/SKILL.md`

## Gate 章节（H2 须与 templates.yaml `code-deliverable` 逐字一致）

| 章节 / 规则 | 要求 |
|-------------|------|
| 正文 | 目录结构、如何运行、与 R 验收的对应关系 |
| code_project | `deliverables/<task_id>/` 可运行脚本 + `README.md` |
| output/ | 运行产出或运行说明 |
| 结构校验 | `min_project_files` ≥ 2、含代码文件、`README.md` 存在 |

## 交付形态

- **不是**单篇 Markdown 报告；是 `deliverables/<task_id>/` 下的 **code_project**

## 执行步骤

1. 读上游 system-design / requirements 的 P0 范围；只做 In Scope 项。
2. 在 `deliverables/<task_id>/` 脚手架工程（参照 arch 契约表）。
3. 实现 + 自测；README 写安装、运行、验证命令。
4. 交付物 Markdown「## 正文」写：目录结构、如何运行、与 R 验收的对应关系。
5. submit 前跑角色方法论中的回归命令（pytest / npm run build 等）。

## 红线

- 禁止空目录或仅 README 无代码
- 禁止把 secrets 写进 deliverable
- 禁止未跑验证就 submit
