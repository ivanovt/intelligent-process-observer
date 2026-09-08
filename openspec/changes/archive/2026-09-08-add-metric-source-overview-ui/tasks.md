## 1. Data Sources Route and Shell

- [x] 1.1 Add the `/data-sources` route and make the existing Data Sources shell item an active `NavLink` while leaving unsupported navigation items disabled.
- [x] 1.2 Add a project-owned Metric Sources page using the existing page header, semantic tokens, Lucide icons, and responsive card/list patterns.

## 2. Capability-backed Source States

- [x] 2.1 Load `GET /api/v1/observation-definition-capabilities` through the existing abort-safe request pattern and implement distinct loading, retryable error, empty, configured, and manual-refresh states.
- [x] 2.2 Render every returned Prometheus source once and in order using only provider type, safe ID, name, and configured-for-Metric-Lens wording, with no endpoint, credential, username, health, or diagnostic projection.
- [x] 2.3 Add empty-state environment guidance with placeholder-only Bearer and Basic examples, multi-source array instructions, backend restart/refresh sequencing, and explicit secret/frontend-environment warnings.

## 3. Integration and Regression Tests

- [x] 3.1 Add rendered route/navigation tests plus loading, retry, empty, refresh, and multiple-source ordering tests that assert prohibited connection details and lifecycle controls are absent.
- [x] 3.2 Extend Metric Lens coverage to prove every one of multiple capability sources is selectable and the chosen exact source ID reaches the existing draft/final aggregate payload without a default or fallback.
- [x] 3.3 Verify request cancellation and stale-response protection remain correct for Data Sources refresh/unmount and all existing Observation Management regressions remain green.

## 4. Architecture and UI Governance

- [x] 4.1 Add ADR-167 to supersede ADR-166's strict MagicPath/v1.1 authority clause while retaining the accepted frontend stack, document accepted UI docs/OpenSpec as authoritative and MagicPath as informative, increment the architecture package version, and update `docs/architecture/12_CHANGELOG.md`.
- [x] 4.2 Update the living `docs/ui/ui_implementation_handoff_v1.md` in place to v1.2 and add `14 Data Sources` with its environment-managed, read-only, multi-source, restart, and credential non-exposure boundaries.
- [x] 4.3 Reconcile v1.2 and ADR-167 authority language in `docs/ui/README.md`, `docs/ui/frontend_ui_stack_adr.md`, and root `AGENTS.md`; preserve and verify the unchanged handoff path in root `README.md` and all other current pointers; state that MagicPath is an informative reference and optional synchronization target rather than an implementation gate.

## 5. Verification

- [x] 5.1 Run focused and complete frontend tests, ESLint, the production build, strict change validation, and `git diff --check`.
- [x] 5.2 Run `make check` as the final local verification before archive or pull-request preparation.
