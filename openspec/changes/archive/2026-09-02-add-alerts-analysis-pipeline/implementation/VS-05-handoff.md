# VS-05 Handoff — bounded optional tools and minimal unsuccessful trace (corrected)

Implemented the run-local Alert optional-tool registry with exactly
`recurrence_concentration_analysis`, `duration_outlier_analysis`, and
`reference_pattern_analysis`. Empty-object requests use immutable current/evidence data;
every first-ten request records an ordinal, repeat use is allowed, and unknown,
scope-expanding, and over-budget requests are rejected before evaluation. Failed and
timed-out tools are non-fatal and project only `{tool, status}` into the built artifact.
The evaluator injection seam now accepts a replacement for every approved name only;
extra or missing keys fail construction, so injection cannot extend the registry. Requests
must supply an empty object `{}`; omitted/`None` arguments are rejected before execution.

## Acceptance evidence

| ID | Boundary / command | Observable assertion | Result |
| --- | --- | --- | --- |
| VS05-AC01 | `tests/test_alert_tools.py::test_optional_registry_enforces_scope_repeats_and_ten_attempt_budget` | Ten repeated calls execute; call 11 is rejected without execution; unknown, scope, and omitted-argument requests execute nothing; exact-name injected replacements run, while extra/missing evaluator maps are rejected before the injected unregistered evaluator can run; ledger ordinals cover every request. | passed (correction) |
| VS05-AC02 | `tests/test_alert_tools.py::test_recurrence_concentration_defaults_zero_and_ties` | Missing counts default to one; zero is not-applicable; tied IDs are lexical and share exact. | passed |
| VS05-AC03 | `tests/test_alert_tools.py::test_duration_outlier_minimum_interpolation_and_strict_threshold` | Seven durations are not-applicable; interpolated quartiles yield 14.5; equality is omitted while 14.6 is an outlier. | passed |
| VS05-AC04 | `tests/test_alert_tools.py::test_reference_pattern_applicability_dominance_and_tie` | One comparison is not-applicable; unique direction wins; a tie is `mixed`. | passed |
| VS05-AC05 | `tests/test_alert_analysis_pipeline.py::test_optional_failure_timeout_continue_with_minimal_trace`; `tests/test_runtime_persistence_integration.py::test_optional_failures_continue_and_persist_only_minimal_trace` | Agent completion remains completed; only failed/timeout tool/status entries persist; diagnostic, ordinal, success, and not-applicable details do not leak. | service passed; PostgreSQL collected/skipped (no `IPO_ALERTS_TEST_DATABASE_URL`) |

Technical verification: `tests/test_alert_tools.py::test_optional_tool_contracts_reject_unknown_and_internal_fields` passes and proves strict public unsuccessful-call models reject executor-only `ordinal`, `diagnostic`, and `ledger` fields.

## Important files and invariants

`contracts.py`, `ports.py`, `tools.py`, `pipeline.py`, and `result_builder.py` establish
the registry/executor seam and public trace projection. The full ledger and tool output
data remain transient. Optional failure alone introduces neither a failure nor partial
reason. Test factories provide a complete exact-name evaluator replacement map rather than
mutating registry internals. Adapter translation and evidence-reference URI work remain deferred.

## Verification

- `cd backend && uv run pytest tests/test_alert_tools.py tests/test_alert_analysis_pipeline.py -q` — 26 passed.
- `cd backend && uv run pytest tests/test_runtime_persistence_integration.py::test_optional_failures_continue_and_persist_only_minimal_trace -q` — collected/skipped; no local PostgreSQL test URL.
- `cd backend && uv run ruff check src/app/alerts tests/test_alert_tools.py tests/test_alert_analysis_pipeline.py tests/test_runtime_persistence_integration.py` — passed.
- `cd backend && uv run ruff format --check src/app/alerts tests/test_alert_tools.py tests/test_alert_analysis_pipeline.py tests/test_runtime_persistence_integration.py` — passed.

## Plan guidance deviations

| Deviation | Evidence / rationale | Coordinator disposition |
| --- | --- | --- |
| none | The correction keeps the injectable registry seam but restricts it to substitution of the fixed three approved evaluators; service and persistence test factories now use that seam. | PENDING |

Known limitation: PostgreSQL proof cannot execute in this correction workspace without
`IPO_ALERTS_TEST_DATABASE_URL`; it is collected and skips normally. The prior candidate's
Coordinator record reports its required PostgreSQL proof passed before this correction.

Commit SHA: `HEAD` (atomic VS-05 correction commit).

Plan change requested: none.

Shared knowledge candidates: none.
