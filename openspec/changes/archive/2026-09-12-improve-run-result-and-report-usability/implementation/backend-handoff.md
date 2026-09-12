# Backend Handoff

## Completed scope

- Tasks 1.1 and 1.2: deterministic report presentation uses labeled, fence-safe inline
  code for opaque values; controls are reversibly displayed, locator paths use dotted
  keys and decimal indexes, and empty hypotheses/limitations use meaning-oriented copy.
- Task 5.1: ADR-172 records the approved dependency-free safe browser renderer. The
  architecture package is versioned 6.9; only the browser-renderer backlog item closed.

## Verification

- `cd backend && uv run pytest tests/test_reporting.py -q` — 40 passed.
- `cd backend && uv run ruff check src/app/reporting/presentation.py tests/test_reporting.py`
  and `uv run ruff format --check src/app/reporting/presentation.py tests/test_reporting.py`
  — passed.
- `openspec validate --all --strict` — passed (pre-existing long-requirement advisories only).

## Integration notes

- No public API, persistence schema, Report Agent contract, production agent behavior,
  dependency, or frontend file changed.
- The frontend safe Markdown-subset renderer is intentionally outside this handoff;
  ADR-172 constrains it to text children, inert HTML/links/unsupported syntax, and exact
  persisted-copy behavior.
- Export, notifications, other renderers, report templates, localization, and a general
  Markdown engine remain Open/Deferred.
