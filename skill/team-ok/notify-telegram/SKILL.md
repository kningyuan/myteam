---
name: notify-telegram
description: "Send progress notifications to Telegram group. Use when: 1) Project starts, 2) Project completes, 3) Task starts, 4) Task completes, 5) Subtask events, 6) Need to report progress to team. Automatically reads bot config from openclaw.json and sends to group -1003735246121."
metadata: '{"openclaw": {"emoji": "📨", "always": true}}'
allowed-tools: "exec"
---

# Notify Telegram Skill

Send project progress notifications to Telegram group.

## 与「群通报」和「适配器私信」的边界

- **本 skill（`notify.py`）**：面向 **Telegram 群** 的 **状态机里程碑**（`project_start` / `task_start` / `task_complete` / `project_complete` 等），配置见 **`openclaw.json`** 与下文 **Configuration**。  
- **执行过程抄送（私信 + 可选流式）**：由 **`~/.openclaw/scripts/openclaw-opencode-adapter`** 在 OpenCode 执行时，通过 **`telegram_sender.send_to_user`** 走 **各 Agent 对应 botToken + `allowFrom` 私聊**；与 **`notify-telegram` 群消息** **不是同一条管道**。启用流式需 **`OPENCODE_ENABLE_STREAMING=true`**（见适配器 `config.py`）。  
- **Agent 间工作消息**：见 **`agent-notify`**（`openclaw agent`），亦不同于群广播。

## Usage

```
skill: notify-telegram
action: notify
project_id: "pro_xxx"
event_type: "project_start"
agent_id: "main"
task_id: "task_001"  # optional
```

## Event Types

- `project_start` - 🚀 Project started
- `project_complete` - 🎉 Project completed
- `task_start` - ▶️ Task started
- `task_complete` - ✅ Task completed
- `subtask_start` - 📝 Subtask started
- `subtask_complete` - ✓ Subtask completed

## Script

```bash
{baseDir}/scripts/notify.py <project_id> <event_type> [agent_id] [task_id]
```

## Configuration

Reads bot configuration from `~/.openclaw/openclaw.json`:
- Bot Token from channels.telegram.accounts.{bot_id}.botToken
- Agent mapping: main→redmacmainbot, product→redmacproductbot, etc.
- Target group: -1003735246121
