# <VS-XX> Handoff

**Status:** IMPLEMENTATION_COMPLETE | BLOCKED
**Commit:** `<sha>`

## Implemented behavior

...

## OpenSpec coverage

...

## Acceptance evidence

| Acceptance ID | Exercised proof level | Full command / node | Observable assertions | Counterexample guard | Result |
|---|---|---|---|---|---|
| VSXX-AC01 | unit / service / PostgreSQL / ... | `path/to/test.py::test_name` or runnable command | exact positive/negative observations | PASS / N/A with reason | PASS |

## Important changes / downstream invariants

...

## Plan guidance deviations

| Deviation | Evidence / rationale | Coordinator disposition |
|---|---|---|
| none | - | PENDING |

For every deviation the Coordinator records exactly `ACCEPT_LOCAL` or
`ESCALATE_STRUCTURAL` before accepting the slice. For `none`, it records `N/A` during
acceptance. The Implementer leaves this column `PENDING` in the slice commit; the
Coordinator updates it in the later metadata commit.

## Verification

...

## Known limitations within approved scope

none | ...

## Plan change requested

none | ...

## Shared knowledge candidates

none | ...
