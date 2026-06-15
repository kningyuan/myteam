# 讨论与头脑风暴专规（圆桌 / 纯讨论）

群组圆桌与纯方案研讨：**只产出观点与方案**，不跑项目编排 execute 流，也不做重工具交付。

## 如何识别

满足以下 **任一** 即进入讨论模式：

- 群组消息以 **`[群组圆桌`** 开头（立论轮、对齐轮、主持汇总）
- 用户明确只要方案/评审/可行性分析，**不要**动手改仓库或跑命令
- Workflow / 流程的 **设计、评审、选型**（尚未进入项目 execute 派活）

**不属于**讨论模式：

- 私聊 / 群聊 @agent 要求**具体执行**（改文件、跑测试、写脚本）→ `interactive-guide.md`
- 收到编排 **AgentPort** 派发（`.trigger/{interaction_id}.request`）→ `worker-template.md`

## 禁止（讨论模式）

- 读取或检查 **`.trigger` / `.response`** 及编排任务流
- 调用 **`submit_result`** 或写入 `.response/`
- `phase=evaluate` / `phase=execute` 与 JSON 响应模板
- 项目编排路径：`deliverables/`（`business/tasks/project/...`）、`task-complete` 等
- **Write / Edit** 改文件、**Bash** 执行命令（含安装、部署、跑测试）

## 允许的工具（调研与阅读）

- **WebSearch / WebFetch**：检索事实与竞品
- **Read / Grep / Glob**：阅读本地材料（勿改文件）
- **Think**（若 CLI 提供）：内部推理

## 输出要求

- 用中文，**结构化**（`##` 小标题 + 列表）
- 聚焦流程、分工、验收或 workflow **设计**建议
- 不要 JSON；圆桌中不要 @ 其他 Agent

### 圆桌主持汇总（若消息标明主持汇总）

- `## 已共识`
- `## 分歧点`
- `## 待用户拍板`
- `## 建议 workflow / 下一步`

最后一轮须含 `## 共识结论` 与 `## 仍存分歧（需用户拍板）`。

## 与交互任务 / 编排的区别（速查）

| 维度 | 讨论 / 圆桌 | 交互任务（私聊/群聊） | 编排 execute |
|------|-------------|----------------------|--------------|
| 典型触发 | `[群组圆桌`、纯评审 | 私聊、群 @ 具体事 | AgentPort 派活 |
| 工具 | 只读 + 调研 | 读写 + Bash | 读写 + Bash |
| 产出 | 对话观点 | 对话 + 可选 workspace 改动 | submit_result + Gate |
| 专规 | 本文件 | interactive-guide.md | worker-template.md |
