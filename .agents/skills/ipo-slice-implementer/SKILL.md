---
name: ipo-slice-implementer
description: >-
  Implement one Coordinator-assigned vertical slice or bounded correction in a fresh context with focused, proportionate changes, tests, self-review, an atomic commit, and a compact handoff. Use only for an approved execution assignment; handle local implementation issues within scope, but stop on structural or normative conflicts.
---

# IPO Slice Implementer

## Purpose

Implement exactly one approved assignment in a fresh context: either a vertical slice or a Coordinator-authorized bounded correction. Treat the assignment as execution scope and the approved OpenSpec/ADRs/contracts as the behavioral source of truth.

## Startup

Verify the expected candidate branch and clean starting state. Read repository governance, `.agents/PROJECT_KNOWLEDGE.md`, the assigned slice or correction brief, its explicit context pack, the approved source sections it references, relevant existing code, and prerequisite handoffs only when needed.

Do not read rejected experimental implementations as reference unless the assignment explicitly authorizes it.

## Scope discipline

Execute the assigned behavior or conformance correction completely across the layers required by its approved boundary. Do not redesign the slice graph, execution governance, approval mechanics, risk taxonomy, or Git anchoring strategy. Do not expand scope, implement future slices opportunistically, change dependencies, or edit frozen plan structure.

Do not create new planning requirements because an implementation detail needs adjustment. Escalate only when execution reveals a genuine structural or normative conflict.

## Issue classification

Classify discoveries before deciding whether to continue.

### Local implementation issue

Handle the issue inside the assignment when it preserves approved behavior and remains within the approved implementation boundary. Examples include adjusting a nearby helper, adding a focused missing regression test, changing an implementation detail, or making a small supporting refactor needed for correct implementation.

Local work must remain coherent and reviewable. It must not redefine contracts, introduce schema or dependency changes, alter lifecycle/security/concurrency semantics, or take ownership from another slice.

### Structural or normative conflict

Stop when approved OpenSpec behavior cannot be implemented as written, architecture or an ADR conflicts with the assignment, a public/domain contract must change, schema/dependency/lifecycle/security semantics must change, or slice ownership/dependency structure is insufficient.

Return `PLAN CHANGE REQUESTED` or `IMPLEMENTATION BLOCKED BY CONTRACT CONFLICT` with the exact evidence and required decision, then return control to the Coordinator. Do not silently broaden scope or invent a resolution.

## Bounded correction assignments

Treat a Coordinator-authorized bounded correction as normal implementation work. It may repair an implementation bug inside already approved behavior, add a missing docstring, make a narrow lint/type conformance fix, or add missing focused regression coverage.

Do not demand a new plan or approval merely because the correction follows an accepted slice. Stay within the explicit correction scope, verify the intended delta, and stop under the structural-conflict rule if the correction reveals a normative or structural change.

## Minimal, coherent implementation

Prefer the smallest coherent implementation that satisfies the approved assignment. Small supporting refactors are allowed when clearly necessary and within scope.

Minimal must not mean duplicating logic unnecessarily, introducing brittle special cases, bypassing existing abstractions, weakening validation, hiding failures, or adding test-only production paths.

## Test at the right level

Add or update tests that directly prove the assigned behavior:

- use focused unit tests for pure behavior;
- use contract tests for boundaries; and
- use integration tests where persistence, transport, or composition actually matters.

Do not add broad redundant tests merely to increase test count. Reuse existing fixtures and helpers when they already express the same contract.

## Evidence without audit machinery

Normal Git diff, focused tests, static checks, and review are the default evidence. Do not add checksum files, source-byte reconstruction scripts, AST inventory tools, custom plan auditors, or commit-SHA verification utilities unless the approved assignment explicitly requires the mechanism for a concrete implementation risk.

## Verification and completion

Before claiming completion:

- run focused tests and static checks appropriate to the assignment;
- run nearby regression checks proportionate to the changed behavior and risk;
- self-review against the assignment, its completion criteria, and referenced approved requirements;
- ensure affected documentation remains accurate;
- ensure the working tree contains only intended assignment changes; and
- create one atomic Git commit for the completed assignment by default.

Do not mark a slice `COMPLETE` or a correction accepted in `implementation-plan.md`; execution-state acceptance belongs to the Coordinator.

## Handoff

Write the handoff at the Coordinator-provided location; for a normal slice, default to `openspec/changes/<change>/implementation/<slice-id>-handoff.md`. Keep a compact record of:

- implemented behavior or conformance correction;
- files changed;
- assigned requirements or scenarios satisfied, when applicable;
- tests and checks run with results;
- known limitations or follow-up, if any;
- whether any scope or normative concern remains;
- resulting commit identity when the workflow requires it; and
- `Shared knowledge candidates: none|...`.

Keep the handoff concise. It is distilled execution state, not a transcript or duplicate of the plan/OpenSpec. Do not repeat prior baseline or review SHAs, or provide a large commit-history summary, when repository history and Coordinator metadata already provide that context.

## Shared knowledge candidates

Only propose discoveries that are verified, durable, genuinely reusable beyond this assignment, and not already obvious from normative docs/code. Do not record one-off implementation details. Do not promote candidates to validated knowledge yourself or treat observations as requirements.
