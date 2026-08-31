# IR-001 Handoff — fractional-second PostgreSQL History chronology

**Status:** IMPLEMENTATION_COMPLETE
**Commit:** `HEAD`

## Implemented behavior

`RuntimePersistenceRepository.load()` now casts the strict JSON UTC `analysis_window`
timestamps to PostgreSQL `timestamptz` before applying ADR-158's strict earlier-end
cutoff and end/start/lexical-LensRun-ID ordering. The existing relational scope,
eligibility filters, bounded newest-lookback query, and oldest-first return order remain
unchanged.

## OpenSpec coverage

The ADR-158 History requirement now has a real PostgreSQL regression covering mixed
whole/fractional UTC seconds, strict cutoff equality, later-end exclusion, event-end
ordering, start-time ordering, lexical LensRun-ID ties, and bounded lookback selection.

## Important changes / downstream invariants

The reader must compare parsed timestamp values, never JSON timestamp strings: a whole
second expressed with `Z` is chronologically earlier than a fractional-second cutoff but
lexically sorts after `.`. The SQL query remains the bounded candidate selector, and the
strict `MetricHistoryCandidate` projection remains the application boundary.

## Verification

- `cd backend && IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test uv run pytest tests/test_metric_history.py tests/test_metric_analysis_pipeline.py -q` — 134 passed (one existing Alembic warning).
- `cd backend && uv run ruff check src/app/infrastructure/persistence/repository.py tests/test_metric_history.py tests/test_metric_analysis_pipeline.py` — passed.
- `cd backend && uv run ruff format --check src/app/infrastructure/persistence/repository.py tests/test_metric_history.py tests/test_metric_analysis_pipeline.py` — passed.
- `git diff --check` — passed.

## Known limitations within approved scope

none.

## Plan change requested

none.

## Shared knowledge candidates

none.
