## Context

The strict run-list projection intentionally validates every durable summary and fails the entire request if any record is invalid. The live development database contains valid records alongside legacy test records without valid analysis windows, so the strict behavior correctly returns `runtime_projection_invalid` but is unsuitable as the sole source for a fault-tolerant overview. The current desktop list also overflows because its shared grid minimums exceed the width of the primary two-column panel.

## Goals / Non-Goals

**Goals:**

- Preserve the strict run APIs while adding an explicit resilient presentation read model.
- Salvage independently valid, safe lifecycle fields without manufacturing analytical meaning.
- Keep latest-item ordering honest when the newest record is limited.
- Correct column geometry and move visual styling closer to the reference hierarchy.

**Non-Goals:**

- Repairing, deleting, or migrating legacy data.
- Weakening strict run-detail/history validation.
- Adding new runtime states, health, severity, time filtering, identity, or authentication.
- Replacing the accepted visual stack or adding dependencies.

## Decisions

### 1. Add a separate resilient runtime endpoint

`GET /api/v1/overview-runtime` will reuse the existing newest-first repository query. It will project each record independently: successful strict summaries become `available`; `RuntimeProjectionInvalid` becomes a `limited` projection built only from whitelisted ORM columns whose values independently satisfy the Overview contract. Query/transaction failures still fail the whole request.

Changing the strict list endpoint was rejected because existing Runs consumers rely on complete contract validity. Silently skipping invalid records was rejected because it would make current-state selection dishonest.

### 2. Use a discriminated union and exact limitation accounting

The response envelope will contain schema version `1.0`, ordered `items`, and `limited_run_count`. Available items wrap the existing public summary unchanged. Limited items carry `availability=limited`, stable identity/correlation, created time, optional independently validated lifecycle values, `analytical_state=null`, and constant safe limitation code. They never carry an analysis window or payload-derived analytical state.

The newest item—available or limited—remains current. Frontend projections will never fall back to an older complete run. This preserves durable chronology while allowing safe execution fields and older markers to remain visible.

### 3. Keep findings strict and activity explicitly limited

Only available summaries with analytical state may become Recent Findings candidates and continue through strict detail reads. Limited items contribute only coverage feedback. Run Activity retains all fourteen newest item positions; independently valid statuses remain exact, while a limited item without valid status uses a separate neutral unavailable representation.

### 4. Replace oversized grid minimums with shared fractional geometry

Header and rows will import one project-owned desktop grid class/structure using `minmax(0, …)` fractional columns and a fixed compact action column. The Action heading will be visually omitted because the chevron's accessible label is sufficient. Runtime-unavailable/limited rows render a cell per column instead of spanning five columns.

### 5. Adapt icons and color without adding semantics

Summary surfaces return to neutral white/surface tokens. Semantic tokens accent numbers and icons only; unavailable values stay neutral. Row icons derive solely from definition composition: Metric-only, Alert-only, mixed, or neutral legacy/empty. Compact analytical and execution treatments keep text with their semantic dot/icon.

## Risks / Trade-offs

- **[Limited projection accidentally leaks invalid content]** → Use a strict new Pydantic union and whitelist only safe scalar ORM fields; never include execution context or validation messages.
- **[Partial validation becomes another domain truth]** → Scope it explicitly to the Overview presentation contract and keep strict APIs authoritative for run detail/history.
- **[Latest limited item hides older analysis]** → Keep this intentionally; falling back would misrepresent stale analysis as current.
- **[Additional endpoint duplicates query composition]** → Reuse the repository summary record/query and isolate only projection behavior.
- **[Grid regresses at real widths]** → Share one column definition between header/rows and test long values, limited rows, and action containment.

## Migration Plan

No schema or data migration is required. Add the new endpoint and tests, switch only Overview to it, then refine presentation. Rollback restores the prior Overview source; strict APIs and stored data remain unchanged throughout.

## Architecture References

- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`: reads remain side-effect free and missing evidence is never normal evidence.
- `docs/architecture/08_observation_analysis_result_contract.md`: only validated analysis produces analytical state/findings.
- `docs/architecture/03_ADR_log.md` ADR-167/168/170: UI authority, durable reads, and trusted boundary remain intact.
- `openspec/specs/observation-run-api/spec.md`: strict list/detail fail-closed behavior is preserved.
- `openspec/specs/overview-monitoring-ui/spec.md` and `overview-monitoring-refinement/spec.md`: existing monitoring and visual behavior is updated only where declared.
