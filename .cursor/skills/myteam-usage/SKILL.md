---
name: myteam-usage
description: Use the myteam multi-agent collaboration framework. Apply when the user asks to run a myteam project, inspect collaboration status, add task types or skills, or reason about System Kernel vs Strategy Registry vs Skill Pack boundaries in this repository.
disable-model-invocation: true
---

# myteam Usage

This Skill is an operator guide for the myteam framework. It must not reimplement Process, AgentPort, Gate, Store, or Observability logic.

## Architecture Boundary

myteam has three layers:

- **System Kernel**: `backend/common/`, `backend/adapter/`, observability API. Owns Process, AgentPort, Gate, Store, contracts, watchdog, retry, token accounting, and recovery.
- **Strategy Registry**: `business/templates/templates.yaml`, `business/config/agents_registry.json`, `business/rules/`. Owns task types, roles, acceptance criteria, evidence rules, and team policy.
- **Skill Pack**: `business/skills/*/SKILL.md` and agent workspace rules. Teaches agents how to perform concrete work.

Rule of thumb:

- Needs persistence, retry, audit, recovery, or deterministic validation -> System Kernel.
- Changes task type, role selection, acceptance criteria, or evidence policy -> Strategy Registry.
- Teaches an agent how to do a concrete job -> Skill Pack.

## Common Operations

### Run a Project

Use the orchestration kernel:

```bash
export MYTEAM_ROOT="$PWD"
export PYTHONPATH="$PWD/backend"
export NO_PROXY="localhost,127.0.0.1,::1"

venv/bin/python3 backend/common/run_kernel.py <project_id> \
  --goal "<project goal>" \
  --mode one_shot \
  --budget 150000
```

Use `--mode recurring` only for bounded iterative projects.

### Start the Hub

```bash
./run.sh start
```

Open `http://localhost:8765` (redirects to `/v2/`). Build first: `cd frontend && npm run build`.

### Inspect Progress

- UI: Projects tab and observability views.
- APIs: `/api/projects`, `/api/obs/...`.
- Runtime truth: `business/tasks/state.db`.
- Human-readable deliverables: `business/tasks/project/<project_id>/deliverables/`.

## Adding Capabilities

### Add a Task Type

1. Add or edit `business/templates/templates.yaml`.
2. Define `outcome_kind`, required sections, deterministic `check_rules`, and `acceptance_criteria`.
3. Verify `backend/common/registry.py` can load the spec.
4. Add or update tests if new check semantics are introduced.
5. Add a Skill only when agents need concrete execution steps.

### Add a Skill

1. Create `business/skills/<skill-name>/SKILL.md`.
2. Keep it focused on execution steps and evidence collection.
3. Do not add scheduling, retry, Gate, Store, watchdog, or contract logic.
4. Ensure the task type exists in the Strategy Registry first.

## Agent Roster

- Template: `business/templates/business-roster.json`
- Merge into runtime: `python3 scripts/bootstrap_business_roster.py`
- Research role id: **`research`** (deprecated: `researcher`)

## Files to Read First

- `README.md` for installation, entry points, and usage.
- `docs/ARCHITECTURE.md` for layer boundaries, `.trigger`/`.response`, and collaboration model.
- `docs/framework-decisions.md` for D1-D19 decision index.
- `docs/0608/15-标准协作模式总结.md` for gold-path workflows and E2E.
- `business/templates/README.md` before changing task types.
- `business/skills/README.md` before authoring Skills.

## Safety

Do not modify runtime state files in `business/tasks/`, `.trigger/`, or `.response/` directly unless explicitly debugging a corrupted local run. Prefer system APIs or `run_kernel.py`.
