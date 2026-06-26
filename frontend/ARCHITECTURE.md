# frontend Architecture

Layered React SPA for the MyTeam Agent Hub. Data flows **down** from pages; HTTP stays at the bottom. Business rules live in Hub (Python), not in the frontend API layer.

## Layer stack

```
Pages          route-level shells, URL params, layout
  ↓
Sections       feature panels within a page (ProjectsSection, ChatSection, …)
  ↓
Components     presentational / focused UI (ProjectDag, AgentChatPanel, …)
  ↓
Hooks          state, subscriptions, side effects (useAgentChat, useResourceQuery)
  ↓
Ports          TypeScript interfaces — pluggable boundaries (ChatPort, ProjectsPort)
  ↓
API modules    thin HTTP clients — one file per domain, no business logic
  ↓
Hub REST       `/api/*` served by Agent Hub (Python)
```

## Directory map

| Layer | Path | Role |
|-------|------|------|
| Pages | `src/pages/` | Top-level routes (`ProjectsPage`, `GroupChatPage`, …) |
| Sections | `src/sections/` | Large feature blocks used by pages |
| Components | `src/components/` | Reusable UI, grouped by domain (`project/`, `chat/`, …) |
| Hooks | `src/hooks/` | React hooks; orchestrate ports + local state |
| Ports | `src/lib/ports/` | Interfaces + default Hub implementations |
| API | `src/lib/api/` | Domain HTTP modules (see below) |
| Lib | `src/lib/` | Cross-cutting utilities (`dataRefresh`, `thinking`, …) |

## API modules (`src/lib/api/`)

Monolithic `api.ts` was split by domain. Each module only serializes/deserializes HTTP — **no** workflow logic, gate rules, or agent orchestration.

| Module | Endpoints (examples) | Types exported |
|--------|----------------------|----------------|
| `client.ts` | — | `hubFetch`, stream helpers, `isAbortError` |
| `projects.ts` | `/api/projects/*`, `/api/obs/projects/*` | `ProjectSummary`, `ProjectDetail`, `TaskDetail`, … |
| `agents.ts` | `/api/agents/*` | `AgentSummary`, `AgentDetail` |
| `chat.ts` | `/api/chat/*` | `ChatMessage` |
| `groups.ts` | `/api/groups/*` | `GroupSummary`, `GroupMessage` |
| `workflows.ts` | `/api/workflows/*`, task-types, delivery-templates, skills | `WorkflowDetail`, `TaskTypeSummary`, … |
| `config.ts` | `/api/config`, `/api/backends`, `/api/obs/summary` | `BackendSummary`, `ObsSummary` |
| `index.ts` | re-exports all of the above | backward-compat barrel |

Import style:

```ts
// Preferred — domain-specific
import { listProjects } from "@/lib/api/projects"
import type { ProjectSummary } from "@/lib/api/projects"

// Also fine — full barrel
import { listProjects, listAgents } from "@/lib/api"
```

`src/lib/api.ts` remains a thin re-export for legacy `@/lib/api` imports.

## Ports (`src/lib/ports/`)

Ports mirror backend **adapter** pattern: hooks and features depend on an interface, not `fetch`.

| Port | Methods | Default impl |
|------|---------|--------------|
| `ChatPort` | `listMessages`, `streamChat`, `cancelChat` | `hubChatPort` → `api/chat` |
| `ProjectsPort` | `listProjects`, `getProject`, `runProject` | `hubProjectsPort` → `api/projects` |

Swap implementations (mock, offline, alternate backend) by injecting a different `ChatPort` / `ProjectsPort` without touching components.

Example:

```ts
import type { ChatPort } from "@/lib/ports/ChatPort"
import { hubChatPort } from "@/lib/ports/hubChatPort"

function useChat(port: ChatPort = hubChatPort) {
  return port.listMessages(agentId)
}
```

## FE / BE boundary

| Concern | Frontend | Backend (Hub) |
|---------|----------|---------------|
| Project DAG / task state | Display `ProjectOverview`, subscribe SSE | Kernel truth in SQLite |
| Gate failures / quality | Render `TaskDetail` | Gate algorithms, scoring |
| Agent chat streaming | Parse SSE chunks, UI state | CLI adapters, session cancel |
| Group roundtable | `detectGroupChatMode` (routing hint only) | Facilitator, turn loop |
| Config / backends | Forms + `updateConfig` | YAML/registry persistence |

**Rule:** If it changes product behavior or validation, it belongs in Hub — not in `src/lib/api/*`.

## Cache invalidation

`dataRefresh.ts` broadcasts resource keys (`projects`, `agents`, `groups`, …). API mutation helpers call `invalidateResources()` after successful writes so `useResourceQuery` subscribers reload.

## Live streams

| Stream | API helper | Transport |
|--------|------------|-----------|
| Agent chat | `sendAgentChat` | SSE via `fetch` + `readStreamWithAbort` |
| Group chat | `sendGroupChat` | SSE (`\n\n` framed) |
| Project progress | `subscribeProjectStream` | `EventSource` |
| Group events | `subscribeGroupEvents` | `EventSource` |

Global agent chat state (`agentChatStream.ts`) survives route changes; cancellation goes through `ChatPort.cancelChat` → Hub → CLI adapter.

## Adding a new feature

1. Add Hub route (Python) if needed.
2. Add types + functions in the matching `src/lib/api/<domain>.ts` module.
3. If multiple consumers need abstraction, extend or add a Port interface.
4. Wire a hook or section; keep components dumb.
5. Export from `api/index.ts` for barrel consumers.

## Build

```bash
cd frontend && npm run build
```

Typecheck: `tsc -b` (project references). Vite bundles `src/` to `dist/`.
