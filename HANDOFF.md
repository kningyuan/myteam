# HANDOFF — myteam

最后更新：2026-06-04（UTC+8）

## Goal

myteam（`/Users/kuanghualong/myteam`）多 agent 协作框架的**异步通知 + 稳定性 + 用户体验修复**，确保群聊通报、私聊执行过程和自动恢复机制正常工作，并通过真实项目运行验证。

## Current Progress（本轮完成）

### 缺陷修复（13 项）

| # | 问题 | 修复 |
|---|------|------|
| B1 | `project_data.py` 中 `send_notification` 调用未定义的 `read_task_data` | 添加 import |
| B2/B3 | `chat_service.py` / `agent_chat.py` 规则文件路径 `skill/` → `skill/rule/` | 路径修正（规则文件已迁移目录） |
| B4 | `notify_service.py:92` — `cancel.wait()` 和 `threading.Thread()` 被合并到同一行 | 分行修复，导致 notify 同步调用时看门狗线程不启动 |
| B5 | 异步通知 `response_file` 机制缺失 | 新增 `_collect_text_and_write_file` 后台线程采集 SSE 并原子写入 |
| B6 | 竞态条件：背景线程直接写 `.response` 文件，执行器可能读到不完整内容 | 改为 `.tmp` + `rename` 原子写入 |
| B7 | evaluate/execute 通知走 `send_project_dispatch` 漏传 `response_file` | 条件判断：有 `response_file` 时走 `send_agent_message` |
| B8 | `workspace-` 空目录 ghost agent | `agent_chat.py` `_scan_agents` 和 `agent_registry.py` 添加空 ID 过滤 |
| B9 | 私聊 SSE 双重重包装：手动 `agent_thinking` + `fanout_stream_event` 再包装 | 改为直接传原始 SSE JSON 给 `fanout_stream_event` |
| B10 | 群通报 `sender=system` 显示为纯文本 | 改为 `sender=agent_id`，渲染为 agent 消息气泡 |
| B11 | 群通报多行格式丢失：`markdown.js` 用空格连接段落行 | 改为 `📋` 检测 + `innerHTML` + `\n→<br>` |
| B12 | 私聊记录不可见：SSE 有时序性，用户连接晚了收不到 | `.chat` 文件持久化 + `GET /api/agents/{id}/chats` API + 前端 `loadBackgroundChats` |
| B13 | 新消息不触发侧栏排序/恢复 | 轮询检测 + `hiddenAgents` 自动删除 + 红点 `new-dot` + 排序优先 |

### 测试修复
- cross_review 测试 4 个：mock `send_agent_message` + 目录正确性修复
- executor 测试 8 个（命名别名 `_read_task_data`/`_write_task_data`/`_project_dir` + `state_quality_gate` 返回值 + 空数据断言）

**最终：70 passed, 0 failed**

### 真实项目测试（3 轮）
1. **「AI团队如何自动不断执行GEO优化」**（旧项目续跑）：
   - INIT → TEAM_CONFIG(8 agents) → TASK_PLAN(9 tasks) → ADD_TASKS → DISPATCH_LOOP
   - task_001(researcher)→3 subtasks ✅
   - task_002(seo) ✅ → task_003(product)→4 subtasks→task_003_01 timeout(600s)
2. **「网站GEO快速评估」**（全新项目从0跑）：
   - TEAM_CONFIG: 15s → 4 agents ✅
   - TASK_PLAN: 11s → 4 tasks ✅
   - EVALUATE: 16s → split→3 subtasks ✅
   - sub_task_001(researcher): 50s ✅ → sub_task_002 timeout(600s)

**验证通过的功能点**：
- 状态机全链路（INIT→TEAM_CONFIG→TASK_PLAN→ADD_TASKS→DISPATCH_LOOP）
- 异步通知 + 后台 SSE + `.response` 文件原子写回
- main agent 私聊 `.chat` 记录（各含 2 步 thinking）
- 项目群通报（agent 气泡、多行 emoji 格式、50+ 条）
- 新消息自动恢复 + 红点 + 排序
- `run.sh start|stop` 启动/停止

## What Worked
- 异步通知（`wait_response=False` + `response_file`）消除 300s 同步阻塞
- `.chat` 文件持久化 + API 读取，克服 SSE 时序不可靠
- 先 `.tmp` 再 `rename` 原子写入，消除执行器读不完整文件的竞态条件

## What Didn't Work / 已知问题
- **agent 处理超时**：opencode CLI 模型推理可能超过 600s 默认 `SUBPROCESS_TIMEOUT`，导致子任务卡死。建议将 `skill/team/task-executor/scripts/executor.py` 的 `SUBPROCESS_TIMEOUT` 调大（如 1800s），或关注模型健康度。
- **模型失效**：`opencode/minimax-m3-free` 已被下架。当前可用模型见系统配置页。
- **可观测性缺口（未修）**：opencode `{"type":"error",...}` 在 `parser.py` 未被捕获为 `EventKind.ERROR`，失败原因不进时间线。
- **超时配置分散**：`skill_config.json` 的 `task_timeout`(3600s) 与 executor.py 内 `SUBPROCESS_TIMEOUT`(600s) 不一致，后者实际生效但不可外部配置。

## 关键文件速查
- 通知服务（后台 SSE + .chat 持久化）：`backend/hub/services/notify_service.py`
- 异步通知桥接层：`skill/team/bridge/myteam_notify.py`
- agent 通知脚本（team_config/task_plan/evaluate/execute）：`skill/team/agent-notify/scripts/notify_agent.py`
- 执行器状态机：`skill/team/task-executor/scripts/executor.py`
- 群通报格式：`skill/team/common/notify_format.py`
- 前端 SSE 处理 + 背景聊天加载：`frontend/app.js`
- 前端 markdown 渲染：`frontend/markdown.js`

## Next Steps

1. **执行器超时调优**：将 `skill/team/task-executor/scripts/executor.py` 的 `SUBPROCESS_TIMEOUT` 增大（建议 1800s）或改为从 `skill_config.json` 读取。
2. **parser error 可观测性**：修 `parser.py` 捕获 `type:error` → `EventKind.ERROR`。
3. **`run.sh` 一键清理僵尸**：增加 `kill_stale` 子命令，清理残留 opencode 进程。
4. **模型统一管理**：用户可在设置页确认所有 agent 使用有效模型（避免 `minimax-m3-free` 下架类问题）。
