## 1. Prerequisite and Derived State

- [x] 1.1 Confirm the implementation branch contains the accepted `add-overview-monitoring-ui` code and verify the existing Overview focused tests pass before refinement begins.
- [x] 1.2 Extend the pure Overview summary projection with explicit latest-run `no_significant_findings` and `uncertain` counts and verify focused tests cover all analytical states, unavailable analysis, never-run Observations, active runs, and failed-plus-analytical overlap.
- [x] 1.3 Add a pure local Observation search projection over name and optional description that preserves input order, and verify focused tests cover trimming, case-insensitive matching, missing descriptions, empty queries, and no matches without API activity.
- [x] 1.4 Extend the Overview data coordinator with last-successful-client-refresh time without changing shared run contracts or polling semantics, and verify focused tests cover definition success, run-history success, automatic polling success, failure without timestamp advancement, and deterministic clock control.

## 2. Dense Monitoring Workspace

- [ ] 2.1 Refactor the Overview into a `max-w-7xl` responsive primary-grid composition with Observations beside the Recent Findings/Run Activity rail at wide widths and the required stacked order at narrow widths; verify component tests assert section order, desktop grid ownership, and preservation of all loading/empty/unavailable/stale sections.
- [ ] 2.2 Implement the compact header and six-card responsive summary with semantic icons/tokens and last-refresh presentation; verify component tests assert exact labels/counts, independent unavailable values, failed-plus-analytical overlap, and honest refresh wording.
- [ ] 2.3 Replace individually bordered Observation cards with a lightweight searchable semantic list using aligned desktop columns and compact narrow rows; verify tests cover column labels, row order, definition/latest-run links, runtime-unavailable and never-run labels, search/no-match/clear behavior, and that search leaves summary and rail content unchanged.
- [ ] 2.4 Implement distinct focusable recent-run markers for all five ObservationRun statuses with keyboard-visible detail and accessible exact-state labels; verify completed and cancelled remain distinguishable without color and no unsupported `partial` marker is rendered.
- [ ] 2.5 Refine the insights rail and Run Activity presentation with visible represented-total and exact pending/running/completed/failed/cancelled counts while retaining existing finding/activity bounds; verify tests prove true-finding-only content, additive incomplete feedback, fourteen-run count consistency, and absence of ObservationRun `partial`.

## 3. Integration and Quality

- [ ] 3.1 Add Overview integration coverage for search during successful and runtime-unavailable states, client refresh time across manual/automatic refresh, responsive information preservation, read-only request behavior, and the exclusion of avatar/global-time-range/fabricated health controls.
- [ ] 3.2 Run `npm run test`, `npm run lint`, and `npm run build` in `frontend/`, resolve refinement regressions, and verify all commands pass without adding dependencies or changing backend code.

## 4. Repository Verification

- [ ] 4.1 Run `make check` from the repository root and verify backend checks/tests, frontend lint/tests/build, and strict validation of both the prerequisite and refinement OpenSpec changes pass before archive or pull-request work.
