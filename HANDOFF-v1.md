# HANDOFF — myteam

最后更新：2026-06-03（UTC+8）

## Goal（当前在做什么）

两条线，**第二条是当前焦点且未完成**：

1. **（已基本完成）排障 + 可靠性修复**：用户在 UI 上跑团队协作 / 持续任务遇到失败和卡死，定位根因并修复。
2. **（进行中 · 设计已重构，方向已定，待开工）通用协作框架重构**：本轮（06-03 晚）用户把焦点从「任务分类(A/B1/B2)」重构为三个痛点——①单 agent 多轮记不住上下文、②要 Telegram 式 UI + 知识引用、③要领域无关的通用协作框架。已收敛出「**对话/记忆进 Store + Context Assembler 抗注意力偏移 + 通用化**」的方向与 P0–P3 路线图（详见下方「设计讨论」章节）。**下一步从 P0 记忆地基开工，但建议先与用户确认一处实现细节（滚动摘要由谁生成 / 检索是否先只做 FTS）。**

## 背景：myteam 是什么

- 路径：`/Users/kuanghualong/myteam`，**非 git 子 worktree**，主仓。
- 定位：一个「LLM agent 团队 规划+执行」框架，**16 个独立 agent**（各自 workspace / 进程 / 可各自配模型），不是单 agent 换帽子。
- 启动：`./run.sh start|stop`，hub 跑在 `127.0.0.1:8765`，前端静态文件实时从磁盘提供（改前端只需浏览器 hard-refresh + 升 `?v=` 版本号，不必重启 hub）。
- 内核：`backend/common/run_kernel.py` → `Process`（`backend/common/process.py`）串行驱动 DAG；`AgentPort`（`backend/common/agent_port.py`）投递 interaction + 两段式看门狗；opencode 适配器在 `backend/adapters/opencode/{adapter.py,parser.py}`。
- UI 发起项目：`POST /api/projects/run` → hub 内 **daemon 线程**跑 `run_project`（见 `backend/hub/api/server.py:583` `_run_kernel_bg`）。**注意：内核是跑在 hub 进程里的线程，hub 一停/重启就中断。**
- 真相库：sqlite，`common.store.Store`。可观测：`common/observability.py` + `/api/obs/...`。

## Current Progress（这次会话做了什么）

### 已提交 `03cb0b1`（fix(reliability)）
1. **opencode 子进程泄漏修复** `backend/adapters/opencode/adapter.py`
   - 根因：opencode 空闲时 `for line in proc.stdout` 阻塞读，看门狗置的 `cancel_event` 不会被检查；且 `proc.kill()` 只杀会话首进程，opencode 子进程被孤儿化（reparent 到 init），跑多了攒一堆僵尸（实测发现跑了 11~13 小时的残留进程）。
   - 改法：加旁路 canceller 线程监听 `cancel_event`，触发即 `os.killpg` 杀**整个进程组**（先 SIGTERM 给 2s 再 SIGKILL），既解除 stdout 阻塞又连子进程一起回收；超时分支与 finally 统一走新加的 `_terminate_group`。
2. **评审通过升级** `backend/common/process.py:~430`
   - 旧：`return status if passed else "needs_review"`（reviewer 批准了但自评因 known_gaps 标了 needs_review 仍停在 needs_review，永远到不了 completed）。
   - 新：`return "completed" if passed else "needs_review"`（reviewer 为权威）。加了单测 `test_review_approve_promotes_low_selfassess_to_completed`。
   - 测试：`backend/common/tests` 全量 **125 passed**。

### 未提交（工作区改动，待 commit）
- `frontend/{app.js,index.html,style.css}`：给项目页「执行过程 → 交互明细」trace 面板**加了「关闭」按钮**（之前点开关不掉，因为根本没有关闭按钮，只能靠切项目消失）。
  - index.html：trace 面板加 `.trace-header` + `#trace-close` 按钮（**注意：close 按钮放在 `#trace-title` 外，因为 `openTrace()` 会用 textContent 覆盖 trace-title**）。
  - app.js：注册 `'trace-close'` DOM id + 绑定点击隐藏面板（在 group-modal-close 绑定处旁边）。
  - 资源版本号 `?v=28 → v=29`。`node --check frontend/app.js` 通过。
  - **下一步可直接 git 提交这批前端改动。**

### 运行环境现状
- hub 已重启、在跑（serves v29）。当前无活动 run。
- 历史僵尸 opencode 已清。

## What Worked
- 用 sqlite store + `ps`/`pgrep` 进程表交叉核对，能精确还原项目卡在哪一步、谁是孤儿进程。
- 直接用 `~/.opencode/bin/opencode run ... -m <model>` 单独探测模型，是定位「模型失效」最快的手段。
- `os.killpg`（配合 Popen 的 `start_new_session=True`）解决 CLI 子进程泄漏。

## What Didn't Work / 重要坑
- **模型 `opencode/minimax-m3-free` 已被 opencode 下架**（之前会话把全部 16 个 agent 一键切到它，6/3 它从可用列表消失 → 所有调用报 `Model not found` → 任务挂）。当前 opencode 真实可用模型：`opencode/big-pickle`、`opencode/deepseek-v4-flash-free`、`opencode/mimo-v2.5-free`、`opencode/nemotron-3-super-free`、`SenseNova/deepseek-v4-flash`、`SenseNova/sensenova-6.7-flash-lite`（flash-lite 执行环节太弱会卡）。用户后来自己在设置页换了模型。
- **可观测性缺口（未修，待定）**：opencode 在 stdout 吐 `{"type":"error",...}`（如 Model not found），但 `parser.py` 没处理 `type:error`，所以失败原因不进时间线/UI，用户只看到「失败」。**建议修**：`parse_line` 捕获 `type:error` → `EventKind.ERROR` 事件，加单测。（这轮问过用户要不要修，用户岔开了话题，未确认。）
- **「持续任务」是假 B2**：`_run_recurring`（process.py:187）是「团队定一次 + 每轮重新 task_plan + 滚动摘要」，但**轮次背靠背瞬间连跑、无真实时间间隔**，`max_cycles` 默认 3 跑完即停；goal 里写的「每3分钟」只是给 LLM 看的文字，**框架没有真正的定时器**。

## 设计讨论（线索 2，进行中 · 已重构方向，未写代码）

> 本轮（06-03 晚）用户**主动把焦点从「A/B1/B2 任务分类」重构为三个具体痛点**，方向升级为「通用协作框架」。旧的 A/B1/B2 + 调度讨论**没废**，被收编为路线图的 P3（见下）。

### 用户提出的三个痛点（本轮的真问题）
1. **单 agent 多轮「记不住上下文」**——感觉每条消息独立。
2. **Web UI 不好看/不流畅/功能缺**——想要 **Telegram 式对话窗 + 知识内容引用**。
3. **想要通用团队协作框架**——不绑定具体业务场景。

### 关键代码核实（已读源码确认，不是猜）
- **只有一条 chat 路径**：`/api/chat/{agent_id}`（server.py:225）→ `base/agent_chat.stream_chat`（仅转发）→ `hub/services/chat_service.ChatService.stream`。
- **续接机制是有的**：`store/sessions.py` 的 `session_store` 按 `(backend, agent, workspace)` 存 `session_id`；下轮给 opencode 传 `-s <id>`（adapter.py:128）；parser 抓 `sessionID`（parser.py:23）。线上 `business/config/session_map.json` 确实有数据 → 会话 ID 在被捕获。**所以「每条消息独立」不是设计如此。**
- **但地基缺口确凿**：Store 的 5 张表（project/task/interaction/run_event/memory，schema 见 store.py:53）**全是「项目执行」维度，没有任何「对话/消息」表**。人↔agent 的对话历史**只寄存在 opencode 自己的 session 里（黑盒）**，myteam 库里没有消息级历史；archive 还是靠前端传 `snapshot` 上来（server.py:269）。→ 记忆不可控、UI 无数据源、换后端不通用。
- `session_map.json` 还有**残留旧 key 格式**（`main:main:...` 这种 adapter 位被写成 agent_id），说明 key 规则改过，历史上可能错配会话。

### 重构定位
从「业务定制 + 依赖 opencode 黑盒会话」→「**对话/记忆一等公民 + 领域无关 + 后端可换**」。单机单人优先，但数据模型按通用/可移植设计。骨相（Process/AgentPort/Store/质量门/幂等/`os.killpg`）保留。

### 核心改动：对话/记忆进 Store（P0 地基）
新增两张表（与现有 5 表并存，`project_id` 可空以支持纯 DM）：
```
conversation(conversation_id PK, kind[dm|group|project], participants(json),
             project_id NULL, title, created_at, updated_at, meta)
message(id PK, conversation_id, seq, role[user|agent|system|tool],
        author("user"|agent_id), parts(json:[{type:text|tool_use|tool_result|citation}]),
        backend, tokens, created_at, meta)
```
- 「知识内容引用」= `message.parts` 里的 `citation`，指向 `memory.id`/交付物路径/另一条 message/URL。
- chat 流程改造：收到用户消息先落 `message(role=user)` → **组 prompt 时从 Store 取历史显式拼装**（不再依赖 opencode `-s`，`-s` 退化为可选优化）→ 产出落 `message(role=agent)`。
- 一步同时解决 #1（记得住、确定性、可移植）+ 为 #2 备好数据源 + 为 #3 解耦后端。

### Context Assembler（回应用户「注意力偏移」关切 — **重要**）
用户明确点出：怕全量历史灌进 prompt 造成注意力偏移（lost-in-the-middle）。**这恰恰是 own_full 优于 opencode `-s` 的理由**——拥有历史才能做上下文工程对抗偏移。P0 记忆层 = 一个 **Context Assembler**，每轮按 token 预算 + 优先级组装，而非「取最近 N 条拼接」：
1. 系统/身份（稳定置顶）
2. 滚动摘要（更早轮次增量压缩）
3. 近窗逐字（最近 K 轮原文，放靠近末尾抓 recency）
4. 检索召回（对 message+memory 检索，先 sqlite FTS 关键词→后续 embedding；引用卡片来源）
5. 置顶事实 pin（用户/main 钉住的关键决策，永远在场）
> 这是把现有 `_build_context`（process.py:364，D16 上游摘要+引用注入）从「任务 DAG」推广到「对话」。

### 本轮已拍板的决策
- **协作形态**：(1) 协调者(main)+平级流水线（增强版），**不做** (2) 真·平级实时对话（会拆掉刚修好的串行/观测/进程管控）。
- **记忆策略**：**own_full + Context Assembler**（我们完全拥有历史 + 智能组装抗偏移），不依赖 opencode `-s`。
- **P0 对话范围**：**先 DM only**（最小闭环，先修好「记得住」）。
- **通用化路径**：agent **按需创建**（`team_config` 缺能力就调 `agent_factory.generate_agent` 造，并放宽 process.py:176 的团队外硬拒绝为「先造再纳」）；task_type 从 `templates.yaml` 写死 → 「通用内建 + 项目级覆盖」。
- **B2 调度（P3 用）**：选 **乙 hub 内置「无睡眠 ticker」**——`next_due_at` 持久化进库，ticker 每 ~30s 扫到点项目→跑一轮短命 cycle-runner→退出；取消复用现有 `_is_cancelled`(process.py:277)+`cancel_event→os.killpg`。**「能取消」是用户硬要求。** cycle-runner 做成独立单元，将来可被 launchd(甲) 复用。周期**用户自定义**（`interval_minutes`，0=手动）。

### 路线图
- **P0 记忆地基**：conversation/message 表 + chat 读写 Store + Context Assembler（own_full、DM only、抗注意力偏移）。← **下一步从这切，最小可用切片**
- **P1 Telegram 式 UI + 引用**：前端从 message 表渲染对话流 + 引用卡片（后端半截 P0 已就绪）。
- **P2 通用化**：按需造 agent + task_type 数据化 + 去业务名册。
- **P3 自适应迭代/调度**（收编旧 B2 讨论）：强制采集步（每轮第一步固定 `task_type=collect` 去爬真实数据）+ `prior_summary`→真实采集数据 + 乙调度器真实节奏。详细一期改造清单见本轮对话（数据层 recurring_sched 表 / 内核拆 run_one_cycle / API run-cycle / 测试）。
- **横切可靠性线**（独立，未排期）：内核移出 hub daemon 线程（durable execution，hub 重启不丢在跑项目）、provider fallback（防 `minimax-m3-free` 那种下架全线挂）。

## Next Steps（给下一个 agent）

1. **P0 记忆地基开工**（用户已同意进入实现方向，但建议先确认一处实现细节再写）：
   - 在 `store.py` 加 `conversation`/`message` 表 + CRUD；`chat_service.stream` 改为「落库 + Context Assembler 组装 prompt」，`-s` 降级为可选。
   - 实现 Context Assembler（系统/摘要/近窗/检索/pin，token 预算）。范围 **DM only**。
   - 验收：对一个 agent 连发 2 条相关消息，第 2 条能引用第 1 条事实；prompt 不随轮数线性膨胀（有摘要/近窗上限）。
   - **已定的实现细节**：滚动摘要 = **当前 agent 顺带生成**（每轮多一步、不另设角色）；检索 = **先只做 sqlite FTS 关键词**（零新依赖，后续再升 embedding）。Context Assembler 五段（系统/摘要/近窗/FTS 召回/pin）按 token 预算组装。
2. **可随时做的小事（旧账，未变）**：
   - `git commit` 当前未提交的前端「trace 关闭按钮」改动（见下文「未提交」段）。
   - （待用户确认）修 parser `type:error` 可观测性缺口。
   - 顺手清 `session_map.json` 里的残留旧 key（`agent:agent:ws` 脏数据）。
   - 提醒/帮用户确认 agent 现在配的模型不是已下架的 `minimax-m3-free`。

## 关键文件速查
- 内核循环 / recurring：`backend/common/process.py`（`run` 105、`_task_plan` 149、`_run_recurring` 187、评审 `_peer_review` ~399、质量门 `_quality_status` ~390）
- 投递 + 看门狗：`backend/common/agent_port.py`
- opencode 适配 / 解析：`backend/adapters/opencode/adapter.py`、`parser.py`
- UI 发起项目（hub 线程跑内核）：`backend/hub/api/server.py:574+`
- 前端项目页 / trace：`frontend/{index.html,app.js,style.css}`
- 测试：`backend/common/tests/`（`pytest backend/common/tests -q`，当前 125 passed）
