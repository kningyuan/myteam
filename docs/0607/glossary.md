# myteam 术语表

| 术语 | 英文 | 定义 |
|------|------|------|
| 项目 | Project | 一次编排执行的完整单元，包含一组有依赖关系的任务。每个项目对应一个 goal。 |
| Agent | Agent | 具备特定角色和技能的 AI 工作者。每个 agent 有独立的工作空间和身份定义。 |
| 任务 | Task | 项目中的最小工作单元，由单个 agent 执行并产出一份交付物。 |
| 目标 | Goal | 用户给出的高层次目标描述，驱动整个编排流程。 |
| 交付物 | Deliverable | agent 完成任务后产出的成果文件（报告、代码、文档等）。 |
| 任务类型 | Task Type | 任务分类，决定了交付物的结构模板和质量门禁规则。 |
| DAG | DAG（Directed Acyclic Graph） | 有向无环图，表示任务间的依赖关系。系统按拓扑序执行。 |
| 门禁 | Gate | 任务完成后的确定性质量检查，验证交付物格式和内容完整性。 |
| 结果 | Outcome | 任务或项目的终态，如 `completed`、`failed`、`blocked`。 |
| 产物 | Artifact | 任务执行过程中产生的中间文件（非最终交付物）。 |
| 交互 | Interaction | agent 和框架之间的一次完整通信周期：请求 → 执行 → 响应。 |
| 动作 | Action | Interaction 的一种类型，表示 agent 需要执行一个具体操作（而非写文档）。 |
| 工作空间 | Workspace | agent 的工作目录，包含身份文件、触发目录和交付物目录。 |
| 注册表 | Registry | agent 和 task_type 的配置中心，定义了每个 agent 的职责边界。 |
| 分诊 | Triage | 任务失败后由 main agent 决策的处理方式：重试、换人或中止。 |
| 重试 | Retry | 任务失败后的重新执行，通常由门禁不通过或看门狗超时触发。 |
| 看门狗 | Watchdog | 监控 agent 执行状态的机制：无响应超时 → 软告警 → 硬终止。 |
| 组队 | Team Config | main agent 根据 goal 选择哪些 agent 参与项目的决策过程。 |
| 任务规划 | Task Plan | main agent 将 goal 拆解为 DAG 任务列表的决策过程。 |
| 模板 | Template | 定义 task_type 交付物结构（章节、必需内容、检查规则）的配置。 |
| 配置 | Config | agent 的运行时设置，包括后端类型、模型、超时参数。 |
| 后端 | CLI Backend | 驱动 agent 的 CLI 工具，如 opencode 或 claude。 |
| 真相库 | Store | SQLite 数据库，存储项目、任务、交互的全部状态（唯一真相源）。 |
| 可观测性 | Observability | 通过 API 查询项目和任务运行状态的能力。 |
| 评审 | Review | agent 间同行评审机制，可选的交付物质量提升环节。 |
| 阻塞 | Blocked | 任务的依赖项未完成时的等待状态。 |
| 预算 | Budget | 项目的 token 消耗上限，超限后项目自动暂停。 |
| 契约 | Contract | 框架和 agent 之间交互数据的结构化协议（Request/Response 模型）。 |
| 适配器 | Adapter | 抽象 CLI 差异的中间层，使系统支持多种 agent 后端。 |
| SSE | Server-Sent Events | 服务器推送技术，用于 Hub 实时展示项目进度。 |
| 循环 | Cycle | recurring 模式下的一次完整执行轮次。 |
| 拆分 | Split | 任务展开：agent 评估复杂度后将一个大任务拆分为多个子任务。 |