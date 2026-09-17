## 1. Retrieval Regression Boundary

- [x] 1.1 Add focused failing tests for the diagnosed verbose-query/relevant-passage pair, strict-path preservation, unrelated and single-term rejection, and exact relaxed admission boundaries; verify the new tests fail against the strict-only retriever for the intended reason.
- [x] 1.2 Add PostgreSQL-normalized distinct query-lexeme projection and deterministic relaxed lexical candidate search, including distinct matched-term count and reused semantic distance; verify focused query-construction and candidate-mapping tests cover punctuation, repeated terms, and fewer-than-two-term queries.
- [x] 1.3 Implement initial-admission-first fallback control and the fixed two-signal relaxed admission rule while preserving candidate limits, deterministic ordering, provenance, whole-passage serialization, and the shared timeout; verify focused retriever tests pass for strict, relaxed, no-match, timeout, and byte/passage-bound scenarios.

## 2. Safe Retrieval Diagnostics

- [x] 2.1 Extend the operational diagnostic allowlist with controlled retrieval strategy and bounded candidate/admission/return counts; verify serialization tests reject or omit unsupported/unbounded content and retain existing secret/query/content exclusions.
- [x] 2.2 Inject the existing emitter and ObservationRun correlation into the concrete curated-retriever construction path without changing framework-neutral retrieval contracts; verify composition and orchestrator tests cover curated and empty fallback construction.
- [x] 2.3 Emit exactly one non-authoritative informational decision event for each successful strict, relaxed, or no-match curated retrieval; verify focused tests assert categories, evaluated-path count representation, correlation, content exclusion, and unchanged retrieval outcomes when emission fails.

## 3. Integrated Verification

- [x] 3.1 Add a PostgreSQL integration regression using the diagnosed `mprm-server`-style scoped document and verbose query plus unrelated and out-of-scope controls; verify the relevant passage is returned only through the relaxed path and exact provenance remains resolvable.
- [x] 3.2 Run the focused curated-retrieval, knowledge executor, diagnostics, composition, and orchestrator test suites and verify all changed boundaries pass without modifying public API, persistence, reasoning, or report contracts.
- [x] 3.3 Run `openspec validate improve-knowledge-retrieval-relevance --strict` and verify the completed change remains structurally valid.
- [x] 3.4 Run `make check` and verify the repository-wide lint, formatting, backend tests, frontend checks/build, and strict OpenSpec validation all pass before archive or pull-request work.
