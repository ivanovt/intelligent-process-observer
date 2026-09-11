## 1. Frontend Dependency and Data Projection

- [x] 1.1 After explicit approval of the dependency proposal, add `recharts@^3.10.1` to the frontend manifest and lockfile and verify `npm install` completes without changing unrelated dependencies.
- [x] 1.2 Add pure Overview projection helpers for latest-run selection, independent summary counts, ordered Observation rows, seven-run row history, five analyzed-run finding candidates, and fourteen-run activity data; verify focused unit tests cover mixed states, failed-plus-significant state, missing analysis, ordering, bounds, and never-run definitions.
- [x] 1.3 Add an Overview data coordinator that loads definitions and run history independently, reuses forward-only sequential run polling, and performs cancellable/cached detail requests for the bounded finding candidates; verify focused tests cover complete success, partial source failure, stale-data preservation, terminal non-regression, detail partial failure, and polling shutdown after a final terminal refresh.

## 2. Monitoring Interface

- [x] 2.1 Implement the Overview page header, four independent summary cards, responsive Observation list, explicit never-run/runtime-unavailable states, and definition/latest-run navigation; verify component tests assert exact counts, semantic badges, seven accessible history markers, ordering, and links for mixed monitoring data.
- [x] 2.2 Implement Recent Findings from Observation-level run-detail artifacts only, including bounded empty and incomplete states; verify component tests prove that hypotheses, Lens-local findings, reports, and execution failures are not promoted into findings and that each displayed finding links to its owning run.
- [x] 2.3 Implement project-owned `RunActivityChart` over Recharts with exact execution-state tokens, chronological data, a text legend, an accessible status-count summary, empty state, and Runs-history link; verify focused tests cover all five execution statuses, the fourteen-run bound, non-visual labels, and absence of analytical-state inference.

## 3. Routing, Refresh, and Integration

- [x] 3.1 Activate the shell Overview navigation at `/overview`, add the route, and redirect `/` to it without changing existing routes; verify routing tests cover root redirect, active navigation state, direct Overview entry, and navigation to Observation and run detail.
- [x] 3.2 Integrate manual refresh and page-level loading, empty, partial, complete-failure, and stale feedback while keeping successful sections visible; verify integration tests cover independent request outcomes, retry actions, active-run refresh updates, and no mutation requests from Overview.
- [x] 3.3 Run `npm run test`, `npm run lint`, and `npm run build` in `frontend/`, fix any Overview regressions, and verify all three commands pass.

## 4. Repository Verification

- [x] 4.1 Run `make check` from the repository root and verify Ruff checks, backend tests, frontend lint/tests/build, and strict OpenSpec validation all pass before archive or pull-request work.
