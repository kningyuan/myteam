# Strategy Registry

`business/templates/templates.yaml` is the business strategy registry for task types. It is configuration, not a Skill and not runtime state.

## Ownership

- System code owns the loader and enforcement path: `backend/common/registry.py`, `backend/common/process.py`, `backend/common/gate.py`.
- This directory owns task-type strategy: deliverable shape, objective checks, outcome kind, and review criteria.
- Skills may explain how to perform a task, but they must not introduce task types that are absent from this registry.

## Loading Path

```text
Process -> registry.get_spec(task_type)
        -> business/templates/templates.yaml
        -> constraints injected into the agent prompt
        -> Gate validates the result with the same spec
```

`templates.yaml` is the single source of truth for task-type constraints. The code loader may derive defaults, but business text and acceptance policy belong here.

## Task Type Shape

```yaml
task-type-name:
  outcome_kind: artifact   # artifact | action; optional, inferred from evidence_url when omitted
  deliverable_template:
    required_heading_level: 2
    sections:
      - name: "Section Name"
        description: "What the agent should cover"
        required: true
        example: "Concrete example text"
  check_rules:
    required_sections:
      - "Section Name"
    file_exists:
      - "relative/path.ext"
    evidence_url:
      host_contains: "example.com"
      url_must_match: "^https://example.com/"
      screenshot_field: "证据截图"
      verify_title: true
    stub_floor: 200
    must_include:
      - "structural token"
  acceptance_criteria:
    - "Used by self-review and peer review"
```

## Field Rules

- `outcome_kind` decides whether the task produces an `artifact` or an `action` outcome. Action tasks must provide hard evidence.
- `deliverable_template.sections` is prompt guidance for the agent.
- `check_rules.required_sections`, `file_exists`, and `evidence_url` are deterministic Gate checks.
- `stub_floor` is only a non-empty/non-placeholder guard. Do not use it as a quality score.
- `must_include` is off by default in Gate unless explicitly enabled by runtime policy. Prefer acceptance criteria for quality expectations.
- `acceptance_criteria` is the shared source for self-review and peer review. If omitted, the registry derives a minimal checklist from required sections.

## Add a New Task Type

1. Add the task type to `templates.yaml`.
2. Choose `outcome_kind` explicitly for action tasks.
3. Define required sections and objective checks.
4. Add `acceptance_criteria` when the default section-derived checklist is too weak.
5. Add a Skill only if agents need concrete execution steps or external-tool instructions.
6. Verify through `backend/common/registry.py` and Gate tests when adding new check semantics.

## Boundary

Do not place Process, AgentPort, Gate, retry, watchdog, persistence, or observability logic in this directory. Those are System Kernel responsibilities.
