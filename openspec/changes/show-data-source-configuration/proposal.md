## Why

The Data Sources screen currently confirms that a Prometheus source exists but does not let an operator inspect its effective connection configuration. Operators need read-only visibility into every currently supported non-secret source field without exposing authentication secrets to the browser.

## What Changes

- Keep each configured Prometheus source in its existing compact card/list presentation by default.
- Add a per-source control that expands and collapses a detail pane containing pretty-formatted JSON for that source's current non-secret configuration.
- Extend the definition-capabilities response with an explicit server-built safe projection of the configured source: `id`, `name`, `base_url`, credential `type`, and Basic-auth `username` when applicable.
- Exclude bearer tokens and Basic-auth passwords from serialization and from all browser-visible state; do not send redacted placeholders that disclose secret presence or shape beyond the non-secret credential type.
- Advance the accepted living UI handoff to v1.6 so its Data Sources visibility rules remain synchronized with the approved API and UI behavior.
- Preserve existing read-only behavior, source ordering, refresh semantics, and Metric Lens source selection.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `observation-definition-api`: Extend Metric source capability entries with a typed, secret-safe configuration projection suitable for read-only inspection.
- `metric-source-overview-ui`: Add an accessible per-source configuration disclosure and pretty-formatted JSON detail view while retaining the compact default presentation.
- `prometheus-metric-provider`: Reconcile the provider's credential-safety contract with the intentional capabilities response by allowing its non-secret source projection while keeping acquisition ports, diagnostics, and secret handling unchanged.

## Architecture References

- `docs/architecture/03_ADR_log.md` — ADR-167 UI authority model and ADR-170 trusted single-user/internal deployment boundary.
- `docs/ui/frontend_ui_stack_adr.md` — accepted frontend visual stack and project-owned component guidance.
- `docs/ui/ui_implementation_handoff_v1.md` — accepted Data Sources placement, environment ownership, refresh behavior, and credential-safety boundary.

## Impact

- Backend public contract: additive fields in `GET /api/v1/observation-definition-capabilities`, produced from an explicit allowlisted projection rather than a raw settings dump.
- Prometheus provider contract: the capabilities response may expose the approved non-secret projection, while Bearer tokens, Basic-auth passwords, provider ports, failures, logs, and diagnostics retain their existing privacy boundaries.
- Frontend: Data Sources types, card rendering, disclosure interaction, JSON presentation, and tests.
- UI documentation: versioned Data Sources guidance updated from v1.5 to v1.6.
- Tests: backend contract/secret-exclusion coverage and frontend interaction/accessibility/rendering coverage.
- Security: source endpoints and non-secret Basic-auth usernames become visible to users of the existing unauthenticated internal UI; bearer tokens and passwords remain server-only.
- Dependencies, persistence, environment schema, provider execution, and source lifecycle behavior are unchanged.
