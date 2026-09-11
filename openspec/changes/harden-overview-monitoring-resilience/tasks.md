## 1. Resilient Backend Projection

- [ ] 1.1 Add strict public available/limited Overview runtime contracts and verify unit tests cover complete items, independently optional lifecycle fields, forbidden extra data, and limitation counts.
- [ ] 1.2 Add per-record resilient projection over the existing newest-first repository records, preserving strict summary output when valid and safe limited output only for `RuntimeProjectionInvalid`; verify valid/legacy mixtures, ordering, invalid analysis windows, and no raw diagnostics.
- [ ] 1.3 Add the read-only `GET /api/v1/overview-runtime` service/API boundary and verify API tests cover mixed success, empty history, persistence failure, side-effect freedom, and unchanged strict run-list/detail fail-closed behavior.
- [ ] 1.4 Add PostgreSQL integration coverage proving valid and legacy/inconsistent runtime records coexist in one successful Overview feed without mutation or fabricated analysis.

## 2. Resilient Frontend Monitoring

- [ ] 2.1 Add frontend contracts/API loading for the resilient feed and update Overview projections to retain newest available-or-limited ordering, field-local availability, limited-current counts, findings candidates, and fourteen-item activity; verify focused tests cover mixed items and no fallback to stale older analysis.
- [ ] 2.2 Update the Overview coordinator and refresh/polling behavior to use the resilient endpoint while leaving Runs screens on strict APIs; verify partial items remain data rather than request failure and infrastructure failures still preserve stale/failed feedback.
- [ ] 2.3 Render limited rows, markers, summary coverage, findings limitations, and activity limitations while preserving every independently safe field; verify missing/inconsistent data never suppresses unrelated valid content or becomes an invented state.

## 3. Visual Alignment

- [ ] 3.1 Replace the overflowing desktop grid minimums with one shared contained header/row geometry, remove the visible Action header, and add an accessible icon-only row affordance; verify header/cell alignment and no overlap at the supported desktop width.
- [ ] 3.2 Restyle summary cards to neutral surfaces with semantic number/icon accents and neutral unavailable treatment; verify analytical and execution token ownership remains separate for zero, available, limited, and unavailable cases.
- [ ] 3.3 Add composition-derived Metric-only, Alert-only, mixed, and neutral legacy icons plus compact dot/icon-and-text state treatments; verify icons describe configuration only and all meaning remains available as text.
- [ ] 3.4 Add focused responsive/accessibility tests for long values, all availability combinations, keyboard marker details, local search, and absence of unsupported avatar, global time range, health, fabricated findings, and ObservationRun `partial`.

## 4. Verification

- [ ] 4.1 Run complete backend and frontend focused suites, frontend lint/build, and strict validation; verify no dependency, migration, destructive-data, or unrelated strict Runs behavior change exists.
- [ ] 4.2 Run `make check` from the repository root and verify every canonical check passes before archive or updating PR #26.
