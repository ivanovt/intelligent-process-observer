# VS-03 Handoff — Jira cursor exhaustion and bounded-volume failure

## Implemented behavior

- The Jira adapter follows enhanced-search cursor pages sequentially, preserving the
  original JQL, fields, and `maxResults: 100`; later requests add only
  `nextPageToken`.
- Each page is validated before its issues are retained: `isLast` must be boolean,
  issues must be a list, non-terminal tokens must be new non-empty strings, and a
  terminal page cannot contain a non-empty token.
- One acquisition accepts exactly 1,000 issues only when terminal. Over-cap and
  non-terminal-at-cap responses return `AlertProviderFailure`, never a truncated
  `AlertRecordsAvailable` result.
- A terminal envelope accepts `nextPageToken` only when it is absent, JSON `null`, or
  an empty string. Falsey non-string values (`0`, `false`, `[]`, `{}`) are malformed
  continuations and return `AlertProviderFailure` rather than a success outcome.
- Existing pipeline mappings remain unchanged: pagination/volume failure fails current
  acquisition and makes a reference acquisition unavailable.

## OpenSpec scenarios covered

VS03-AC01 through VS03-AC04.

## Important files/contracts

- `backend/src/app/infrastructure/jira/adapter.py`: private cursor validation and
  bounded acquisition loop; no provider-port or Alert result contract changes.
- `backend/tests/test_jira_alert_provider.py`: request-ledger, envelope, cap, and
  current/reference propagation evidence.

## Verification

Correction verification:

`cd backend && uv run pytest tests/test_jira_alert_provider.py tests/test_alert_analysis_pipeline.py -q` — 48 passed.

`cd backend && uv run ruff check src/app/infrastructure/jira tests/test_jira_alert_provider.py` — passed.

`cd backend && uv run ruff format --check src/app/infrastructure/jira tests/test_jira_alert_provider.py` — passed.

`git diff --check` — passed.

Original VS-03 implementation verification:

`cd backend && uv run pytest tests/test_jira_alert_provider.py tests/test_alert_analysis_pipeline.py -q` — 47 passed.

`cd backend && uv run ruff check src/app/infrastructure/jira tests/test_jira_alert_provider.py` — passed.

`cd backend && uv run ruff format --check src/app/infrastructure/jira tests/test_jira_alert_provider.py` — passed.

`git diff --check` — passed.

## Downstream invariants

The record cap counts raw returned issues before mapping, so malformed individual
records cannot bypass the bound. A failed page is not retained, and no later page is
requested after an inconsistent envelope or cap violation. Current/reference terminal
semantics continue to be owned by the existing pipeline.

## Known limitations within approved scope

Retries, retry delays, attempt/acquisition deadlines, and parallel fetching remain
deferred to VS-04 and VS-05.

Original VS-03 commit SHA: `e79ac3dbe97817e0e259d3f42930222814109777`.

Correction commit SHA: `HEAD` (the atomic correction commit containing this updated handoff).

Plan change requested: none.

Shared knowledge candidates: none.
