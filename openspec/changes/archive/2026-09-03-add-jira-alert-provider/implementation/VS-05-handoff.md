# VS-05 Handoff — Jira retry and failure classification

## Implemented behavior

- Each failed Jira page now receives at most two retries, and only `httpx` connection
  failures or HTTP 429/502/503/504 are eligible. Deadline expiry and every other
  transport, response, decode, envelope, pagination, and volume failure remains
  terminal.
- Retry waits use raw `Retry-After` fields: exactly one positive decimal ASCII value,
  with only surrounding SP/HTAB stripped, selects its integer seconds through 15.
  Duplicate, combined, signed, fractional, date, zero, and other unusable forms use
  the fixed 0.5/1.0-second fallback; a usable value above 15 returns typed timeout.
- The Retry-After cap comparison is bounded before integer conversion. Arbitrarily long
  valid decimal values, including values with leading zeroes, therefore return typed
  timeout without a conversion exception, wait, or retry.
- A wait and its next full 15-second attempt must fit the single 60-second acquire
  deadline. The wait itself is cancellably bounded by remaining acquire time; no
  later retry or page starts after exhaustion.
- Terminal diagnostics remain fixed categories/status codes and never retain response
  body, header, URL, or credential text. Existing current timeout/failure and
  reference-unavailable pipeline behavior is unchanged.

## OpenSpec scenarios covered

VS05-AC01 through VS05-AC07.

## Important files/contracts

- `backend/src/app/infrastructure/jira/adapter.py`: page-local bounded retries, raw
  Retry-After parser, deterministic sleeper seam, and acquire-deadline admission.
- `backend/tests/test_jira_alert_provider.py`: status/error attempt matrix, raw-header
  grammar, exact waits, deadline edge/cumulative budget, safe diagnostics, and
  pipeline outcome regression coverage.

## Verification

`cd backend && uv run pytest tests/test_jira_alert_provider.py tests/test_alert_analysis_pipeline.py -q` — 59 passed, including a 5,000-digit valid oversized Retry-After regression.

`cd backend && uv run ruff check src/app/infrastructure/jira/adapter.py tests/test_jira_alert_provider.py` — passed.

`cd backend && uv run ruff format --check src/app/infrastructure/jira/adapter.py tests/test_jira_alert_provider.py` — passed.

`git diff --check` — passed.

## Downstream invariants

- Retry counters reset for every page, while the monotonic acquisition deadline stays
  shared by pages, complete attempts, and retry waits.
- Retry-After parsing deliberately uses `response.headers.raw`; convenience combined
  header accessors would violate the exactly-one-field requirement.
- Exhausted retryable work with time remaining remains a provider failure; hard timeout,
  excessive usable delay, and failed deadline admission remain provider timeouts.

## Known limitations within approved scope

No operator documentation or final whole-change conformance work was added; those remain
VS-06 responsibility.

Commit SHA: `HEAD` (this atomic VS-05 correction commit).

Plan change requested: none.

Shared knowledge candidates: none.
