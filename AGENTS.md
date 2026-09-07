# Agent Instructions — Intelligent Process Observer

These instructions apply to coding agents working in this repository. They are repository-wide unless a future, explicitly approved nested `AGENTS.md` narrows them for a subsystem.

## 1. Project intent

This repository implements the MVP of Intelligent Process Observer, a modular-monolith system for intelligent multi-agent observation, anomaly analysis, and supervision of technological processes.

Keep the implementation intentionally small. Do not add infrastructure, abstractions, frameworks, or dependencies only because they may be useful later.

## 2. Sources of truth and precedence

Use these sources for different kinds of decisions:

1. `docs/architecture/` is authoritative for architecture, runtime semantics, component boundaries, contracts, ADRs, and open/deferred architectural decisions.
2. `openspec/changes/<change-id>/` is authoritative for the approved scope and behavior of the active implementation change.
3. `openspec/specs/` contains accepted functional behavior accumulated from completed changes.
4. Source code is the implementation of the approved architecture and specifications.

Within the architecture package, use this precedence when documents conflict:

```text
newer ADR
  > current concept / architecture / contract document
  > older example / working note
```

Items explicitly marked `Open` or `Deferred` are not requirements. Never silently choose a value or behavior to close an open architectural decision.

### Known documentation synchronization item

The architecture backlog predates some implementation-stack decisions made for this workspace and may still list database technology or workflow/orchestration technology as open. For implementation tooling, follow the approved workspace stack in this file and `docs/development-guide.md`: PostgreSQL + SQLAlchemy/Alembic and deterministic Python/`asyncio` orchestration. Do not use that stale backlog entry as permission to substitute another stack, and do not edit the architecture package without explicit user approval.

## 3. Language policy

- Write code, identifiers, code comments, repository instructions, development documentation, pull-request text, and OpenSpec artifacts in English.
- Existing architecture documents are intentionally retained in Bulgarian and remain normative.
- Do not translate or duplicate the architecture package unless explicitly requested.

## 4. Code documentation

- Document every public class and interface with a concise docstring explaining its purpose and function.
- Document every public method that forms part of an interface with a concise docstring explaining its purpose and function.
- Keep docstrings minimal and behavior-focused; do not restate the implementation line by line.

## 5. Context-loading policy

For a small, mechanical, unambiguous change:

1. Read this root `AGENTS.md`.
2. Inspect only the code and documentation directly relevant to the task.

For an OpenSpec or behavioral change:

1. Read this root `AGENTS.md`.
2. Read `docs/architecture/README.md` as the architecture navigation map.
3. Identify and read only the relevant architecture, ADR, and contract documents.
4. Read the active OpenSpec change and its artifacts.
5. Implement only after the user has explicitly approved the planning artifacts.

If a conflict, missing architectural decision, or unresolved `Open`/`Deferred` item blocks correct implementation, stop and report it. Do not invent the missing decision.

## 6. Change classification

Use the lightweight two-track model.

### Direct change — OpenSpec is not required

A direct change is acceptable when expected behavior is already unambiguous and no new contract or behavior is being defined. Examples:

- typo or documentation correction;
- formatting;
- a small local UI adjustment with already-defined behavior;
- an obvious local bug fix whose expected behavior is already documented;
- refactoring without behavior or contract changes;
- adding or correcting a test for already-defined behavior.

### OpenSpec change — required

Use OpenSpec for any new or changed behavior, including:

- a new feature or endpoint;
- API or structured-contract changes;
- semantically meaningful database-schema changes;
- new or changed pipeline stages;
- lifecycle, failure, partial-result, retry, or execution semantics;
- new agents or tools, or changes to agent/tool boundaries or budgets;
- behavior spanning multiple modules;
- behavior that requires new acceptance criteria;
- changes that touch or depend on unresolved architectural questions.

When uncertain whether a change is behavioral, prefer proposing the classification to the user instead of guessing.

## 7. OpenSpec governance

The project uses the OpenSpec `core` profile.

OpenSpec complements architecture documentation; it does not replace it. Do not copy large architecture sections into OpenSpec. Reference relevant files and ADRs instead.

For significant changes, proposal/design artifacts must identify relevant architecture references or explicitly state `N/A` when none apply.

### Human approval gate

Planning and implementation are separate approval points:

```text
proposal + specs + design + tasks
            ↓
       human review
            ↓
     explicit approval
            ↓
          apply
```

Do not begin production implementation before explicit approval.

After approval, scope and behavioral semantics are frozen for that implementation pass. You may update task completion state and make implementation-level choices that stay inside the approved scope. If the implementation reveals that scope, behavior, specs, or design must materially change, stop, explain why, and wait for approval before changing the OpenSpec planning artifacts.

### Autonomous execution continuity

When the user instructs an agent to autonomously execute an approved implementation
plan until completion or an escalation condition:

- Do not return a final response while a delegated implementer, reviewer, verifier,
  or correction task for that execution is active or awaits Coordinator disposition.
- A progress or status update is not a terminal response; send it through the
  commentary channel and continue coordination.
- Before returning a final response, reconstruct execution state from the
  implementation-plan execution table, Git status and recent commits, required
  handoffs, and the status of any delegated agents.
- Return a final response only after every plan slice and required final
  verification/review step is accepted, or after a documented Coordinator
  stop/escalation condition is reached.
- When ending short of completion, record the exact stop/escalation reason in the
  mutable execution metadata of the implementation plan before responding.

### Archive convention

For this repository, archive the completed OpenSpec change inside its feature branch before opening or merging the pull request:

```text
feature/<change-id>
  → plan
  → human approval
  → implement
  → make check
  → archive the OpenSpec change
  → review canonical spec updates
  → pull request
  → CI/review
  → squash merge to main
```

Do not archive an incomplete or unapproved change merely to make validation pass.

## 8. Architecture-document safety

Treat `docs/architecture/` and ADRs as read-only by default.

If implementation requires an architectural change:

1. stop;
2. describe the conflict or missing decision;
3. wait for explicit architectural approval;
4. only then update the relevant ADR/docs if the user explicitly asks you to do so;
5. update the active OpenSpec change when required;
6. resume implementation only after the updated plan is approved.

Never change architecture documentation silently to fit an implementation.

## 9. Git safety

The normal branch model is:

```text
main
  └── feature/<openspec-change-id>
```

One OpenSpec change should normally map to one feature branch with the same kebab-case identifier. The initial workspace bootstrap is the explicit exception and uses `chore/bootstrap-workspace`.

Without additional approval, agents may:

- create a local feature/chore branch;
- edit files within an approved scope;
- run local checks and tests;
- create local commits.

Explicit user approval is required before an agent may:

- push to GitHub;
- create or update a pull request;
- merge a pull request;
- modify `main` directly;
- force-push or rewrite remote history.

Pull requests are squash-merged into protected `main` after required CI passes.

## 10. Dependency policy

Do not add, remove, or replace dependencies without explicit user approval.

You may propose a dependency change. The proposal should state:

- the dependency and intended version range;
- why it is needed;
- the problem it solves;
- whether the requirement can reasonably be implemented without it;
- the impact on the agreed technology stack.

Only modify `pyproject.toml`, `package.json`, or related lockfiles for dependency changes after approval.

## 11. Database and migration safety

Within an already approved schema change, agents may:

- generate Alembic migrations;
- edit those migration files;
- run normal migrations against the local development database.

Explicit approval is required before destructive database operations, including:

- dropping or resetting the local database;
- destructive manual schema operations outside an approved migration;
- bulk deletion or irreversible cleanup of local data.

Do not invent domain tables during infrastructure/bootstrap work.

## 12. Approved implementation stack

### Backend

- Python >= 3.13, managed with `uv`
- FastAPI
- Pydantic and `pydantic-settings`
- PostgreSQL
- SQLAlchemy async
- Psycopg 3
- Alembic
- Ruff for linting and formatting
- pytest

### Frontend

- React
- TypeScript
- Vite
- npm
- ESLint

Do not add a UI library, Tailwind, a frontend test framework, a Python formatter separate from Ruff, a message broker, workflow engine, or distributed worker system during bootstrap.

The application is a modular monolith. Deterministic orchestration remains plain Python/`asyncio` unless a later explicitly approved decision changes that. PydanticAI is the approved MVP agent-framework integration mechanism (ADR-152); it must not replace framework-neutral domain contracts, deterministic orchestration, or domain-owned execution constraints. Add its production dependency only within the approved scope of the first production agent feature that requires it.

## 13. Frontend / UI implementation

Before planning, implementing, or reviewing frontend/UI changes, read:

1. `docs/ui/README.md`
2. `docs/ui/frontend_ui_stack_adr.md`
3. `docs/ui/ui_implementation_handoff_v1.md`
4. relevant domain/runtime contracts under `docs/architecture/`

### Frozen UI direction

UI Direction v1.0 is frozen.

Do not silently change:

- information architecture;
- product terminology;
- analytical-state semantics;
- execution-state semantics;
- finding vs hypothesis semantics;
- evidence vs knowledge semantics.

Minor technical adjustments for accessibility, responsive fit, browser behavior,
or real data length are allowed when they preserve the accepted semantics.

### Accepted frontend visual stack

Use:

- React
- Tailwind CSS 4
- shadcn/ui
- Base UI primitives
- Lucide React
- Recharts
- TanStack Table only when advanced table behavior is genuinely needed.

Do not introduce an alternative visual/component framework without an explicit
architecture/UI decision.

### Styling rules

- Treat `docs/ui/ui_implementation_handoff_v1.md` as the implementation reference.
- Prefer project-owned semantic components over one-off Tailwind markup.
- Use semantic design tokens for domain states instead of scattering raw colors.
- Third-party UI primitives must adapt to the frozen design, not redefine it.
- Keep generic primitives separate from ObserveAI domain components.

Examples of project-owned semantic components include:
`AnalyticalStateBadge`, `ExecutionStatusBadge`, `LensCard`, `FindingCard`,
`HypothesisCard`, `EvidenceChip`, `RelationshipChip`, and `KnowledgeChip`.

### Domain semantic guardrails

Execution state and analytical state are independent.

Do not map:
`completed | partial | failed`
to
`no_significant_findings | uncertain | significant_findings_present`.

A failed execution means unavailable analytical evidence; it does not mean that
an anomaly or significant finding was detected.

Do not introduce new severity, confidence, probability, root-cause, or
recommendation semantics unless the relevant architecture contracts are changed first.

Findings are observational-evidence grounded.
Hypotheses are explanatory and may use knowledge references.
Do not visually or structurally collapse those concepts.

### Charts and tables

- Use Recharts through project-owned chart components.
- Do not expose chart-library details throughout feature code.
- Use TanStack Table only for screens requiring capabilities such as sorting,
  filtering, pagination, column visibility, or row selection.
- Simple dashboard rows/lists should remain lightweight project components.

## 14. Canonical local commands

Use the root `Makefile` as the canonical command interface:

```bash
make setup
make db-up
make db-down
make backend
make frontend
make lint
make format
make test
make check
```

Before requesting a pull request, run `make check` and report any failures accurately. Do not claim checks passed if they were not executed successfully.

`make check` is expected to cover:

- Ruff linting;
- Ruff formatting check;
- backend pytest;
- frontend ESLint;
- frontend production build;
- strict OpenSpec structural validation.

## 15. Secrets and environment files

- Root `.env` is local-only and must not be committed.
- Root `.env.example` documents backend/PostgreSQL configuration.
- `frontend/.env` is local-only and must not be committed.
- `frontend/.env.example` documents browser-visible `VITE_*` values.
- Never put secrets in `VITE_*` variables or client-side source.

## 16. Nested AGENTS.md maintenance

Start with this root file only.

If stable, subsystem-specific instructions begin repeating across multiple changes, suggest extracting them into a nested `AGENTS.md` located near that subsystem. Do not create a nested `AGENTS.md` automatically. Wait for explicit approval.

Do not use nested agent instructions as a substitute for architecture documentation or feature specifications.

## 17. Reusable review and validation skills

Repository-owned reusable review skills live under `.agents/skills/ipo-*`. OpenSpec-generated skills remain under `.agents/skills/openspec-*` and may be regenerated by `openspec update`; do not edit generated OpenSpec skills to add project-specific behavior.

Use the following workflow for non-trivial OpenSpec changes:

```text
openspec propose
  → ipo-review-plan
  → explicit human approval
  → openspec apply
  → make check
  → openspec-verify-change (when installed)
  → ipo-review-implementation
  → human triage / targeted fixes
  → ipo-verify-findings
  → archive
  → PR
```

### `ipo-review-plan`

Run after planning artifacts are generated and before human approval. It is report-only and checks OpenSpec artifacts against architecture/ADRs, open/deferred decisions, scope, behavioral requirements, design boundaries, and task/test completeness.

### `ipo-review-implementation`

Run after implementation and local verification, preferably in a fresh reviewer session. It is report-only and independently checks approved behavior, architecture boundaries, implementation diff, tests, migrations/persistence integrity where applicable, scope, complexity, and code-documentation quality.

### `ipo-verify-findings`

Run after targeted fixes to previously accepted review findings. It is report-only and must stay bounded to the known findings and regressions introduced by their fixes. Do not restart a broad review unless the user explicitly requests one.

### Official OpenSpec verify workflow

The project recommends installing the optional `openspec-verify-change` workflow in addition to the core OpenSpec workflows. Use it after implementation as a standard plan-versus-code verification signal, then use `ipo-review-implementation` for the repository-specific architecture and quality review.

Review skills do not authorize implementation changes. Findings require human triage; the implementation agent fixes only findings the user accepts.

A change must not be archived while unresolved `BLOCKER`, `HIGH`, or `MEDIUM` implementation-review findings remain, unless the user explicitly accepts the risk.

See `docs/development-workflow.md` for the concise contributor workflow and skill usage.
