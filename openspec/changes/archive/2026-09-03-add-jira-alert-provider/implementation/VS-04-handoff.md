# VS-04 Handoff — Jira hard deadlines and cancellation

## Implemented behavior

- Each acquisition fixes one 60-second monotonic deadline. Before every page attempt,
  the adapter requires at least a complete 15 seconds to remain; less time returns
  `AlertProviderTimeout` without constructing or sending that attempt. Exactly 15
  seconds remains admissible.
- Each admitted attempt streams and completely reads the response body under a separate
  15-second cancellable deadline. The production runner uses `asyncio.wait_for`; the
  stream context closes the response on cancellation before the typed timeout escapes.
- The acquisition deadline is not reset between pages. An expired operation ends the
  acquisition with `AlertProviderTimeout`, with no later page attempt. No retry or
  `Retry-After` policy was added.

## OpenSpec scenarios covered

VS04-AC01 through VS04-AC05.

## Important files/contracts

- `backend/src/app/infrastructure/jira/adapter.py`: private monotonic and cancellable
  deadline seams; the existing provider outcome and pipeline contracts are unchanged.
- `backend/tests/test_jira_alert_provider.py`: controlled clock, deadline runner,
  cancellation-observable streamed body, cross-page budget, admission, and current /
  reference pipeline outcome evidence.

## Verification

`cd backend && uv run pytest tests/test_jira_alert_provider.py tests/test_alert_analysis_pipeline.py -q` — 53 passed.

`cd backend && uv run ruff check src/app/infrastructure/jira/adapter.py tests/test_jira_alert_provider.py` — passed.

`cd backend && uv run ruff format --check src/app/infrastructure/jira/adapter.py tests/test_jira_alert_provider.py` — passed.

`git diff --check` — passed.

## Downstream invariants

- Deadline timing is adapter-owned and the pipeline continues to distinguish a current
  typed timeout (`current_query_timeout`) from an unavailable reference
  (`reference_unavailable`).
- A complete attempt includes headers and body read; the response stream context is
  exited on cancellation. HTTPX phase defaults remain defense in depth rather than the
  normative total-duration owner.
- The injected monotonic and deadline-runner seams are infrastructure-private test
  seams. Production construction retains the default monotonic clock and cancellable
  `asyncio.wait_for` runner.

## Known limitations within approved scope

Retry classification, retry counts/waits, `Retry-After`, and retry-budget admission
remain deferred to VS-05.

Commit SHA: `HEAD` (this atomic VS-04 commit).

Plan change requested: none.

Shared knowledge candidates: none.
