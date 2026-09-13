## 0. Prerequisite baseline

- [x] 0.1 Archive/synchronize the completed `add-curated-knowledge-retrieval` predecessor on its feature branch and bring its canonical-spec update into this stacked branch; verify strict validation no longer reports archive-refusal INFO for the two `MODIFIED` requirement headers.

## 1. Architecture and Observation contract

- [ ] 1.1 After explicit architectural approval, record the narrow ADR-173 supersession for independently optional per-service scope versions, legacy interpretation, and rollback limitation; verify architecture references are consistent.
- [ ] 1.2 After explicit UI-direction approval, update `docs/ui/README.md` and the living handoff to v1.10 with per-service entry, review pairing, and version-free suggestion semantics; verify the handoff remains consistent with the approved API and ADR.
- [ ] 1.3 Introduce strict canonical per-service scope contracts plus legacy shared-scope normalization; verify tests reject empty/duplicate/blank/mixed shapes and preserve each legacy service's prior version meaning.
- [ ] 1.4 Extend Observation create/replacement/read and JSONB persistence to accept legacy inputs but return/write only the canonical per-service shape; verify API and PostgreSQL round-trip tests for heterogeneous versions, legacy definitions, unscoped definitions, and atomic rejection.

## 2. Frozen retrieval eligibility

- [ ] 2.1 Freeze each service/version entry at run initialization and apply metadata-first eligibility independently for each service; verify PostgreSQL tests for mixed versions, exact labels, no-version entries, excluded services, global knowledge, legacy equivalence, and an explicitly versioned scope matching an unversioned document tag for that same service.
- [ ] 2.2 Verify a definition edit after run initialization cannot change that run's per-service retrieval eligibility and scope remains absent from finding/overall-state inputs and public retrieval contracts; run focused execution and reasoning integration tests.

## 3. Observation Management UI

- [ ] 3.1 Replace the shared version field with one optional version input visibly paired with each selected service in Create/Edit and review, preserving draft order and per-row edits/removal; verify frontend interaction tests for two different versions, no-version entry, validation, hydration, serialization, and responsive fit.
- [ ] 3.2 Keep scope suggestions service-ID-only: accept a suggested service as unversioned and preserve any existing service's operator-entered version; verify frontend tests for acceptance, dismissal, stale responses, and no implicit version assignment.

## 4. Integrated verification

- [ ] 4.1 Exercise existing legacy and new heterogeneous scopes through API persistence, frozen run retrieval, and exact approved-document eligibility; verify no document-version, citation, lifecycle, evidence, or retrieval-budget regression in focused PostgreSQL tests.
- [ ] 4.2 Run `make check` and `openspec validate per-service-knowledge-scope-versions --strict`; resolve failures and obtain independent implementation review before archive or pull-request preparation.
