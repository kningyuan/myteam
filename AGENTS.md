# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

myteam is a lightweight **multi-agent collaboration platform**: a Web Hub (chat / agent management / groups / observability) plus a declarative **orchestration kernel** that decomposes a `goal` into a task DAG, runs it across agents with deterministic gating, retries, and triage. Agents are driven through the **opencode CLI** via an adapter layer (extensible to other CLIs like Codex).

Codebase comments, docstrings, and commit messages are in Chinese. Design rationale lives in `docs/ARCHITECTURE.md` and `docs/framework-decisions.md` (decisions are referenced throughout the code as `D1`–`D19`, `F1`). **Framework freeze** (L1/L2 kernel + Hub): `docs/FRAMEWORK-FREEZE.md` — new capability goes to `business/workflows/` and `business/skills/`, not kernel refactors.

## Commands

```bash
# Web Hub (UI + chat + observability) — http://localhost:8765 → /v2/, binds 0.0.0.0, uvicorn reload=True
./run.sh start
./run.sh stop

# Orchestration kernel — run one project end-to-end (does NOT need the Hub running)
export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend" NO_PROXY="localhost,127.0.0.1,::1"
venv/bin/python3 backend/common/run_kernel.py <project_id> \
  --goal "..." --mode one_shot|recurring --budget 150000 [--max-cycles 3] [--review] [--split]
# exit 0 only when status == completed

# Use Codex CLI instead of opencode
venv/bin/python3 backend/common/run_kernel.py <project_id> \
  --goal "..." --backend Codex --budget 150000

# Tests. PYTHONPATH=backend is required — tests import the `common`/`hub` packages.
PYTHONPATH="$PWD/backend" venv/bin/python3 -m pytest backend -q

# Single test
PYTHONPATH="$PWD/backend" venv/bin/python3 -m pytest \
  backend/common/tests/test_gate.py::test_registry_loads_real_types -q
```

No linter/formatter is configured (no ruff/black/mypy/Makefile). `run.sh` auto-creates the venv path expectation, sets `PYTHONPATH=backend` + `MYTEAM_ROOT`, and `pip install`s deps if missing. **CLI backends are external dependencies** — opencode/Codex must be installed and its model provider/auth configured separately (myteam holds no model tokens). The kernel shells out to the configured CLI (`--backend opencode|Codex`).

## Architecture: two orthogonal flows

**A) Chat / group (human ↔ agent), streaming:**
```
frontend/ → hub/api/server.py → hub/services/chat_service → base/agent_chat
          → adapter/registry → adapters/opencode → unified AgentEvent → SSE to UI
```

**B) Orchestration kernel (goal → task DAG), batch:**
```
run_kernel.py → Process (state machine: DAG schedule / failure / retry / triage)
              → AgentPort (interaction lifecycle, watchdog, idempotency, token metering)
              → agent_transport (worker prompt → opencode/Codex subprocess → AgentEvent)
              → Gate (contract + format + completeness, deterministic)
              → Registry (task_type constraints ← business/templates/templates.yaml)
              → Store (SQLite truth: business/tasks/state.db)
Observability API (hub/api/observability_api.py) is read-only over the same SQLite + run_event SSE.
```
The kernel does **not** depend on the Hub. Run the Hub alongside it only to watch progress (`/api/obs/...`); both read the same SQLite DB.

## Invariants — do not violate these

**Adapter isolation** (the core abstraction; `docs/ARCHITECTURE.md` §10): the only two cross-CLI data contracts are `RunRequest` and `AgentEvent` (`backend/adapter/`).
- `adapters/<cli>/parser.py` is the **only** place allowed to know a CLI's raw output format.
- The service layer (`hub/services/`, `base/`) must never contain `opencode` or `subprocess`.
- The UI must never reference CLI-specific fields (`part.text`, `sessionID`, raw opencode JSON) — it consumes only the `thinking` SSE event's `type`.
- Adding a CLI = new `adapters/<cli>/` dir + parser + update `agent_transport._default_adapter()`. No UI changes needed.
- Backend selection: `run_kernel.py --backend opencode|Codex`; per-agent backend in `agents_config.json`.

**Interaction contract** (kernel side; `backend/common/contracts.py`, decisions D11/D5/D15): framework and agent exchange exactly one pair of Pydantic models — `InteractionRequest` / `InteractionResponse` — as a discriminated union over `kind` (`team_config | task_plan | evaluate | execute | review | triage`).
- **Structure lives in code** (Pydantic contracts); **content constraints live in config** (`templates.yaml`).
- Agents write results back via `submit_result.py`, which validates against the contract **locally and atomically before writing** the `.response` file. There is no JSON "rescue" / repair path — invalid output is rejected, not salvaged. Do not reintroduce one.
- `Gate` validates an outcome with the **same** registry spec that was handed to the agent (`registry.get_spec(task_type)`) — the down-link and the check-link share one source.

## System / Strategy / Skill — where new capability goes

The collaboration framework is deliberately **not** one big Skill (`docs/ARCHITECTURE.md` §12). Three layers with a hard boundary:

| Layer | Location | Holds |
|-------|----------|-------|
| **System Kernel** | `backend/common/`, `backend/adapter/`, `hub/api/observability_api.py` | Process, AgentPort, Gate, Store, contracts, observability — anything that must be tested, recovered, audited, retried, persisted |
| **Strategy Registry** | `business/templates/templates.yaml`, `business/config/agents_registry.json`, `business/rules/` | task_type definitions, role roster, acceptance criteria, evidence rules |
| **Skill Pack** | `business/skills/*/SKILL.md`, agent workspace `AGENTS.md`/identity files | how an agent performs a specific kind of work |

Decision rule: if failure corrupts system state → System Kernel. If it changes task type / role selection / acceptance → Strategy Registry. If it only affects one task's quality → Skill. **A new task_type must be added to `templates.yaml` first**; you cannot make `Process` recognize a task by writing only a Skill.

## Config & paths

`MYTEAM_ROOT` (= repo root) is the single root for both `backend/hub/paths.py` (server) and `backend/common/paths.py` (kernel). `backend/base/system_config.py` is a deprecated shim re-exporting `store.system_config`.

- **System config — `config/`**: `system_config.json` (port, default backend/model, `backends.opencode.cli_path`, model list — auto-generated on first load), `skill_config.json`. Override the opencode binary via `system_config.backends.opencode.cli_path` or `OPENCODE_CLI_PATH` (default `~/.opencode/bin/opencode`).
- **Business config + runtime — `business/`**: `config/` (agents_config, agents_registry, groups, session_map, `.env`), `workspaces/workspace-<agent_id>/`, `tasks/state.db`, `tasks/project/<id>/deliverables/`.

**Almost everything operational is gitignored** (`config/*.json`, all of `business/workspaces|tasks|config`, `*.log`, `state.db`). A fresh checkout has no agents, no DB, no business data — these are per-environment state generated at runtime. Agent roster template: `business/templates/business-roster.json` (merge via `scripts/bootstrap_business_roster.py`). Research role id is **`research`** (legacy `researcher` is deprecated). Only `main` (which makes `team_config`/`task_plan`/`triage` decisions) plus agents you actually use need a populated workspace. An agent runs without `AGENTS.md`/`IDENTITY.md`/`SOUL.md`/`MEMORY.md`, but with degraded output quality.

**Deliverable scaffold** (`deliverable_guarantee.scaffold_markdown_deliverable`): prewrites `# title` + empty `## required_sections` only; task intent goes via `req.intent` in the worker prompt, not into the markdown file.

## Conventions

- **Commits** follow Chinese conventional-commit style: `feat(ux):`, `fix(reliability):`, `refactor(css):`, `polish(ui):`, `docs(architecture):`.
- The Cursor rule `.cursor/rules/karpathy-guidelines.mdc` is `alwaysApply` and governs how to edit: minimum code that solves the problem (no speculative abstraction/config); surgical changes (touch only what the request requires, match existing style, don't refactor working code or delete pre-existing dead code); surface assumptions and tradeoffs before implementing; define a verifiable success criterion (write/run the test) rather than "make it work".
