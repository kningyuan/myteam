# Hub API Contract (frozen surface)

> Web UI (`frontend-v2`) depends on these URLs and SSE event names. **Additive fields only** — do not rename or remove without a migration plan.

## REST (chat / groups)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/agents` | Agent list |
| GET | `/api/agents/{id}/messages` | DM history; optional `thinking[]` on agent replies (`meta.thinking`) |
| GET | `/api/agents/{id}/chat` | SSE stream (query: `text`, …) |
| GET | `/api/groups` | Group list |
| GET | `/api/groups/{id}` | Group detail + `messages[]` (recent 50) |
| GET | `/api/groups/{id}/chat` | SSE (`sender`, `text`, `mode`, `rounds`, …) |
| GET | `/api/groups/{id}/chat/status` | `{ active, … }` |
| GET | `/api/groups/{id}/events` | Group fanout SSE |

## REST (execute / obs — frozen)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/obs/interactions/{iid}/timeline` | Project execute thinking tree |
| GET | `/api/obs/interactions/{iid}/events` | Execute SSE |
| GET | `/api/obs/projects/{id}/overview` | Project overview |

## SSE event names (must not rename)

### DM / single-agent chat

- `thinking` — payload in `data` (step_start, tool_use, text, …)
- `done`, `error`

### Group chat

- `thinking`, `text`, `done`, `error`
- `roundtable_detached`, `notify_detached`
- Fanout on `/api/groups/{id}/events`: `group_message`, `roundtable_*`, `thinking`, …

### Execute (obs)

- Timeline rows via REST; live via `run_event` on obs streams — **do not change** `ProjectExecTree` mapping without regression tests.

## Message shapes (additive)

### DM `ChatMessage`

```json
{ "role": "user|assistant", "content": "...", "thinking": [ { "type": "..." } ] }
```

### Group `GroupMessage`

```json
{
  "id": "m_…",
  "sender": "user|agent_id",
  "text": "…",
  "timestamp": 0,
  "mentions": [],
  "in_reply_to": "m_…",
  "roundtable": true,
  "roundtable_phase": "thinking",
  "roundtable_round": 0,
  "turn_meta": {},
  "thinking": [ { "type": "tool_use", "name": "…" } ],
  "roundtable_meta": { "artifact_type": "best_practice", "agenda": "…", "facilitator": "main", "participants": [], "cycles_run": 1 }
}
```

圆桌终稿：`roundtable_meta.artifact_type=best_practice` 表示已产出「本题最佳实践」摘要（见 `roundtable_user_decision_summary` 或 transcript）。

## Persistence rules

| Mode | Write | Read (API) |
|------|-------|------------|
| DM | Store `conversation dm:{agent}` + `meta.thinking` | GET messages |
| Group / roundtable | `groups.json` + Store dual-write `group:{id}` | GET group (json + optional Store overlay) |
| Execute | SQLite `run_event` / timeline | obs APIs only |

## Feature flags

| Flag | Default | Effect |
|------|---------|--------|
| `MYTEAM_HUB_GROUP_READ_STORE=1` | off | GET group merges thinking from Store; full Store read when entries include `meta.group_entry` |

## Smoke checklist (real environment)

1. Hub up: `curl -s http://localhost:8765/api/agents | head`
2. DM: send message → thinking streams → refresh → thinking visible on last assistant message
3. Group @agent: reply + thinking → refresh
4. Roundtable @all: detached → status active → messages grow → phase labels + thinking expand
5. Project: run → execute tree shows tools/milestones
6. `python3 scripts/test_group_chat_stability.py` exits 0
