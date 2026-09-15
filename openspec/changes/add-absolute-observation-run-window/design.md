## Context

See `proposal.md` for motivation and `specs/observation-runs-ui/spec.md` for observable behavior. The launch API already consumes concrete aware UTC `analysis_window.from` and `analysis_window.to` values and validates forward, non-future intervals. The frontend currently owns the two relative input forms and resolves both into that unchanged wire shape.

The main implementation hazard is JavaScript date parsing: a zone-less date-time string passed to `Date` may be interpreted as browser-local time, while permissive parsing or UTC construction can normalize invalid calendar values. Absolute input therefore needs an explicit strict UTC conversion boundary rather than relying on ambient timezone behavior.

## Goals / Non-Goals

**Goals:**

- Extend the existing client-side time-range model with a discriminated absolute variant.
- Convert exact operator-entered UTC wall-clock fields to canonical ISO UTC timestamps deterministically.
- Reuse the existing range validation and launch request path.
- Keep validation logic isolated and unit-testable with the existing injected clock.

**Non-Goals:**

- Changing the run API, execution contracts, persistence, provider acquisition, reference periods, or run-history presentation.
- Supporting arbitrary IANA zones, numeric offsets, locale-formatted free text, a calendar library, or broader Grafana date math.
- Retaining separate hidden drafts for all three modes after the operator switches modes.

## Decisions

### 1. Add an explicit absolute variant to the time-range discriminated union

The client input model will add `{ kind: 'absolute'; from: string; to: string }` beside the existing preset and expression variants. `resolveTimeRange` remains the single conversion boundary and returns the existing `{ from: string; to: string }` wire shape.

This keeps mode-specific state impossible to confuse at compile time and leaves the API type unchanged. A separate absolute-window launch request was rejected because it would duplicate a contract that already expresses the required behavior.

### 2. Treat date-time control components as UTC by construction

The dialog will expose two `datetime-local` controls under an `Absolute UTC` radio mode, visibly label each endpoint as UTC, and set one-second stepping. The word `local` in the HTML input type describes its zone-less value syntax; the application will not interpret that value in the browser's local zone.

The resolver will strictly parse the control syntax into numeric calendar components, construct the instant with UTC semantics, and compare the resulting UTC components back to the input. This round trip rejects impossible dates that JavaScript would otherwise normalize. Minute-only control values may represent `:00`; supplied seconds are retained, and canonical output uses `toISOString()`.

Appending `Z` and relying only on built-in permissive string parsing was rejected because browser/runtime parsing differences and calendar normalization make validation less explicit. Adding a date library was rejected because the bounded conversion does not justify a dependency.

### 3. Reuse one captured clock instant and common interval validation

Each resolution attempt will call the injected clock once. After mode-specific resolution, absolute values will pass through the same common checks as presets and expressions: valid current clock, `from < to`, and `to <= now`. Successful preview and confirmation both produce canonical UTC values; confirmation resolves again so future validation uses the instant governing that launch attempt.

Absolute fields will start empty when the mode is selected, making an intentional interval selection necessary. A failed launch leaves the current absolute values intact through the dialog's existing state behavior.

Prepopulating absolute fields from the relative default was rejected because it can make a fixed historical selection look intentional when it was derived from a moving current instant.

### 4. Keep the interaction inside the existing Runs dialog and component vocabulary

The third radio option and its two existing project-owned `Field`/`Input` controls will extend `TimeRangeChooser`; no route, modal, state library, shared design-system primitive, or dependency is needed. Focused tests will cover exact UTC output, invalid calendar input, missing endpoints, order/future validation, unchanged relative modes, accessible labels, submit enablement, and retained values after launch failure.

## Risks / Trade-offs

- [Users may assume the zone-less browser control uses their local timezone] → Label the mode and both fields as UTC, include concise UTC guidance, and preview the canonical `Z` timestamps before confirmation.
- [Native date-time control appearance varies by browser] → Depend only on its standardized value shape and accessible input semantics; keep parsing and correctness in project-owned code.
- [An invalid date may be normalized silently by JavaScript] → Use strict component extraction plus UTC component round-trip validation.
- [An interval can become future-facing between preview and submit] → Resolve and validate again at confirmation, while the backend remains authoritative.

## Migration Plan

Deploy the frontend and UI-documentation update without database or backend migration. Existing clients, requests, run records, relative presets, and expressions remain compatible. Rollback consists of reverting the frontend/UI-documentation change; no stored data requires transformation.

## Architecture References

- `docs/architecture/03_ADR_log.md` — the design follows ADR-167 by versioning the intentional UI interaction and ADR-168 by reusing the established on-demand launch boundary.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — the change continues to pass one concrete frozen UTC analysis window into the existing execution flow.
- `docs/ui/frontend_ui_stack_adr.md` — the implementation reuses project-owned React controls and adds no alternative framework or dependency.
- `docs/ui/ui_implementation_handoff_v1.md` — the existing Runs History and Launch information architecture, concrete-UTC submission rule, and relative modes are preserved and extended in place.
