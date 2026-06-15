# 交互任务专规（私聊 / 群聊 @agent）

用户通过私聊或群组 @你 下达的具体任务：可调研、读写文件、跑命令、改代码、产出结果。

## 如何识别

- Hub 私聊（DM）中的用户消息
- 群组 @mention 后的任务型请求（非 `[群组圆桌` 主持流程）
- 用户明确要求「帮我做 / 改 / 查 / 跑」类具体事

**不属于**本模式：Process 经 AgentPort 派发的 workflow execute（见 `worker-template.md`）。

## 禁止（交互模式 — 框架硬约束）

- 读取或依赖 **`.trigger/`、`.response/`** 编排任务流
- 调用 **`submit_result`** 或写入 **`.response/{interaction_id}.response`**
- `phase=evaluate` / `phase=execute` 与编排 JSON 响应模板
- 写入 **`business/tasks/project/*/deliverables/`**（编排项目交付物目录；用户指定的 workspace 路径除外）

## 允许的工具

完成用户任务所需的全部工具，包括但不限于：

- **Read / Grep / Glob**：读代码与文档
- **Write / Edit**：改文件
- **Bash**：跑测试、安装依赖、执行脚本
- **WebSearch / WebFetch**：调研

## 交付方式

- 以**对话正文**汇报结果（结构化 `##` 小标题 + 列表）
- 若修改了文件，说明路径与变更摘要
- **不要** JSON 交卷；编排任务由 Process 另行派发，与用户私聊/群聊无关
