# 团队规则

## 文件说明

| 文件 | 说明 |
|------|------|
| `universal-rules.md` | 所有 Agent 的基本行为准则 |
| `brainstorming-guide.md` | 头脑风暴模式专用（独立于项目协作） |

## 架构说明

**新架构（executor 流程引擎）**：
- 流程控制由 `team-ok/task-executor/scripts/executor.py` 负责
- Agent 只负责思考和返回 JSON，不调用任何 skill 脚本
- 旧版 `worker-template.md` 已删除（被 executor 取代）
