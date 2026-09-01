# Implementation Plan — <change-name>

**Status:** DRAFT | REVIEWED | HUMAN_APPROVED | IN_PROGRESS | COMPLETE | BLOCKED
**Artifact type:** Non-normative execution plan
**Approved OpenSpec change:** `<change-name>`
**Candidate branch:** `<branch>`

## Authority and constraints

This file describes how the approved change will be implemented. It does not redefine what must be implemented. Accepted ADRs/normative contracts and the approved OpenSpec remain authoritative.

After human approval, slice structure and behavioral proof are frozen. Acceptance IDs,
approved sources, GIVEN/WHEN/THEN assertions, proof levels, counterexample guards, and
ownership may not be added, removed, merged, renumbered, or changed. Only execution
evidence/results against unchanged obligations and other explicitly mutable execution
metadata may be updated by the Coordinator. Structural changes require re-planning,
independent plan review, and human re-approval.

Slice execution state follows `PLANNED -> READY -> IN_PROGRESS -> COMPLETE`; `BLOCKED`
records a defined stop/escalation. The Coordinator commits readiness and `IN_PROGRESS`
metadata before delegation, the Implementer starts from that clean commit and creates the
slice implementation/handoff commit. The Coordinator commits `ACCEPT_LOCAL`/`N/A`
deviation dispositions before high-risk review (`ESCALATE_STRUCTURAL` stops execution),
then records accepted evidence, completion, and newly ready slices in a final metadata
commit after review.
Every clean-boundary assertion includes untracked files, for example
`test -z "$(git status --porcelain=v1 --untracked-files=all)"`.

## Slice graph

```text
VS-01 -> VS-02 -> VS-03
```

## Execution overview

| Slice | Goal | Depends on | Risk | Status | Commit | Handoff |
|---|---|---|---|---|---|---|
| VS-01 | ... | none | normal | PLANNED | - | - |

## Slice definitions

### VS-01 — <name>

**Behavioral goal:** ...

**OpenSpec coverage:** requirement/scenario/task IDs ...

**Dependencies:** ...

**Vertical boundary:** input -> processing -> observable result ...

#### Change map

| Path / symbol | Action | Slice responsibility |
|---|---|---|
| `path/to/file.py::Symbol` | add | ... |

**Contracts consumed/changed:** ...

**Non-goals:** ...

#### Acceptance evidence

These proof obligations translate approved normative behavior into slice-local evidence.
Valid sources are approved OpenSpec requirement clauses/scenarios or accepted normative
ADR/contract clauses. Tasks are supplementary traceability only; process-only tasks
belong in the completion gate. These obligations do not add or change requirements.

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS01-AC01 | normative clause / scenario; task trace if useful | discriminating fixture | exercised boundary | exact observable and negative assertions | unit / service / ASGI / PostgreSQL / adapter / migration | one full `path/to/test.py::test_name` or runnable command per claimed level |

**Counterexample guards:** optional mapping from an acceptance ID to a plausible wrong
implementation that its fixture/assertions must fail.

#### Technical verification (when needed)

Approved design/task constraints that govern implementation technique but are not
normative observable behavior. Give full runnable nodes/commands but no acceptance IDs;
their checks belong in the completion gate. Otherwise write `N/A`.

#### Implementation sketch (optional)

Illustrative and non-normative. Include only when it clarifies a high-risk or ambiguous
interface, control flow, transaction, algorithm, adapter, or migration seam. Normally
limit this section to 5-25 lines; otherwise write `N/A — <reason>`.

```text
input -> validated boundary -> behavior -> observable result
```

**Focused verification commands:** exact focused and nearby regression commands expected
for this slice ...

**Context pack:** exact docs/ADRs/spec sections/code areas, direct-dependency handoffs,
and inherited invariants to read; avoid cumulative predecessor history ...

**Handoff expectations:** include evidence/results for every acceptance ID, actual paths
or symbols changed, deviations from the forecast change map, downstream invariants, and
the standard handoff metadata ...

**Risk:** normal | high-risk

**Completion gate:** all `VS01-AC*` obligations have passing evidence; focused and nearby
regression commands pass; scope/non-goal audit passes; required high-risk review returns
`SLICE REVIEW PASS`; one atomic implementation commit and handoff exist; Coordinator
acceptance metadata is committed separately ...

## Coverage matrix

| OpenSpec requirement/scenario/task | Owning slice | Verification |
|---|---|---|
| ... | VS-01 | ... |

## Execution notes

Mutable Coordinator-owned execution metadata only. Do not place new requirements or redesign decisions here.
