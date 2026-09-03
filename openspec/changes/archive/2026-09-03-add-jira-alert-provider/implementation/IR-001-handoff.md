# IR-001 Handoff — Strict raw Jira URL validation

## Implemented behavior

- Jira site URL validation now rejects whitespace and ASCII control characters from
  the original configured string before `urlsplit` can normalize them away.
- Any colon in the raw URL authority is rejected, including empty explicit-port syntax.
- Existing accepted root and `/jira` forms still derive the same pathless Jira origin;
  REST-origin derivation, authentication, provider behavior, and public contracts are
  unchanged.

## OpenSpec scenarios covered

- Configure Jira: malformed optional configuration, valid provider composition, and
  unsafe-target rejection at the provider-construction boundary.

## Important files/contracts

- `backend/src/app/infrastructure/jira/configuration.py`: strict pre-parse URL guard.
- `backend/tests/test_jira_alert_provider_configuration.py`: valid-form, raw syntax,
  full ASCII-control, empty-port, and provider non-construction regressions.

## Verification

- `cd backend && uv run pytest tests/test_jira_alert_provider_configuration.py tests/test_jira_alert_provider.py -q` — 93 passed.
- `cd backend && uv run ruff check src/app/infrastructure/jira/configuration.py tests/test_jira_alert_provider_configuration.py` — passed.
- `cd backend && uv run ruff format --check src/app/infrastructure/jira/configuration.py tests/test_jira_alert_provider_configuration.py` — passed.
- `git diff --check` — passed.

## Downstream invariants

Validation operates on raw syntax before URL parsing. Canonicalization remains limited
to hostname case and the already approved root/trailing-slash and `/jira` variants.

## Known limitations within approved scope

None.

Correction commit SHA: `HEAD` (resolve as the commit containing this handoff).

Plan change requested: none.

Shared knowledge candidates: none.
