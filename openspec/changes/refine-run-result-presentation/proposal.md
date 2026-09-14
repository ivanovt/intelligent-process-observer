## Why

Run-detail results currently make dense finding traceability immediately visible, let a short limitations card stretch with the neighboring findings card, and render report findings with little visual hierarchy for their factual details. This makes completed runs harder to scan without improving the available evidence.

## What Changes

- Group every finding's Evidence and Relationship reference controls in one accessible `References` disclosure that starts collapsed and preserves each individual reference's existing on-demand resolution.
- Keep the Summary limitations/availability card compact at its intrinsic content height rather than stretching to match the Key findings card.
- Add safe bold emphasis in rendered report findings for deterministic finding labels and factual tokens: displayed finding numbers, Metric/Lens identifiers, timestamps and durations, and numeric measurements with their units. The exact persisted Markdown remains copyable without browser-side mutation.
- Extend the dependency-free safe Markdown presentation subset to render renderer-owned strong emphasis as semantic `<strong>` text while preserving inert handling of raw HTML, links, and unsupported syntax.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `observation-runs-ui`: Refine run-detail disclosure, Summary-card layout, and safe report presentation while preserving artifact and traceability semantics.
- `report-generation`: Mark deterministic report finding labels and factual presentation tokens for strong emphasis without altering the underlying analytical content or report safety boundary.

## Architecture References

- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`
- `docs/ui/frontend_ui_stack_adr.md` (ADR-167 UI authority)
- `docs/ui/ui_implementation_handoff_v1.md` (Run Detail v1.8 traceability and safe-report rules)

## Impact

- Frontend run-detail components, safe Markdown parser/renderer, and their tests.
- Backend deterministic report presentation renderer and report-generation tests.
- No API, persistence, dependency, lifecycle, analytical-state, or execution-semantics changes.
