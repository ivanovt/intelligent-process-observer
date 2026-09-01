---
name: ipo-slice-implementer
description: >-
  Implement exactly one approved vertical slice in a fresh context, including focused tests, self-review, an atomic commit, a compact handoff, and candidate shared knowledge. Use only when a coordinator delegates a ready slice; do not change frozen plan structure or invent resolutions for contract or specification conflicts.
---

# IPO Slice Implementer

## Purpose

Implement exactly one approved vertical slice in a fresh context. Treat the slice card as execution scope and the approved OpenSpec/ADRs/contracts as the behavioral source of truth.

## Startup

Verify the expected candidate branch and a clean starting state after the Coordinator's
committed `IN_PROGRESS` metadata transition. Read repository governance,
`.agents/PROJECT_KNOWLEDGE.md`, the assigned slice in `implementation-plan.md`, its
explicit context pack, the approved source sections referenced by that slice, relevant
existing code, and prerequisite handoffs only when needed.

Clean means no tracked, staged, or untracked residue:
`test -z "$(git status --porcelain=v1 --untracked-files=all)"`.

Do not read rejected experimental implementations as reference unless the slice explicitly authorizes it.

## Scope discipline

Implement the slice completely across the layers required by its vertical boundary. Do not redesign approved behavior, expand scope, implement future slices opportunistically, change dependencies, or edit frozen plan structure.

Treat the slice change map and implementation sketch as grounded execution guidance,
not normative internal APIs. A local path or symbol adjustment is allowed when it stays
inside the approved vertical boundary and acceptance obligations; record the adjustment
in the handoff. A change to observable behavior, contracts, slice ownership,
dependencies, or proof obligations requires escalation rather than reinterpretation.
Acceptance IDs, sources, assertions, proof levels, counterexample guards, and ownership
are frozen structural content; do not add, remove, merge, renumber, or weaken them.

If implementation exposes a real contract/specification conflict or requires a structural plan change, stop and return `PLAN CHANGE REQUESTED` or `IMPLEMENTATION BLOCKED BY CONTRACT CONFLICT` with evidence. Do not invent a resolution.

## Verification and completion

Before claiming completion:
- run the slice's focused tests/checks;
- run required nearby regression checks;
- self-review against every assigned OpenSpec requirement/scenario and every slice
  acceptance ID;
- record the concrete test/command result that proves each acceptance ID and confirm its
  required proof level was exercised rather than substituted with a narrower mock;
- record the exercised boundary, full command/node ID, observable assertions, and
  counterexample-guard result for every acceptance ID;
- confirm discriminating fixtures and negative assertions would fail the counterexample
  guards identified by the plan where present;
- ensure documentation affected by the slice remains accurate;
- ensure the working tree contains only intended slice changes;
- create one atomic Git commit for the completed slice by default.

Do not mark the slice `COMPLETE` in `implementation-plan.md`; that belongs to the Coordinator.

## Handoff

Write `openspec/changes/<change>/implementation/<slice-id>-handoff.md` with a compact record of:
- implemented behavior;
- OpenSpec scenarios covered;
- acceptance evidence keyed by every assigned slice acceptance ID;
- important files/contracts changed;
- deviations from the forecast change map or implementation sketch, or `none`;
- verification commands/results;
- downstream invariants that are not obvious from the code;
- known limitations within approved scope;
- commit SHA;
- `Plan change requested: none|...`;
- `Shared knowledge candidates: none|...`.

Keep the handoff concise. It is distilled execution state, not a transcript.
Leave Coordinator deviation dispositions `PENDING`; the Coordinator records them in a
later metadata commit after independent verification/review.

## Shared knowledge candidates

Only propose discoveries that are verified, durable, reusable beyond this slice, and not already obvious from normative docs/code. Do not promote them to validated knowledge yourself. Never treat candidate observations as requirements.
