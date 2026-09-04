---
name: ipo-implementation-planner
description: >-
  Create a non-normative, risk-proportionate implementation plan for an already approved OpenSpec change. Use before coding a change that warrants execution planning to choose the minimum sufficient vertical-slice graph, preserve requirement traceability and reviewability, and stop on source conflicts or unresolved decisions.
---

# IPO Implementation Planner

## Purpose

Convert one already-approved OpenSpec change into the simplest safe, executable plan. Optimize for correctness, reviewable vertical progress, early integration where useful, and fresh-context implementation. Do not implement production code.

## Source of truth

Read repository governance first, then the complete approved OpenSpec change and all referenced accepted ADRs / normative architecture and contracts. Read `.agents/PROJECT_KNOWLEDGE.md` as advisory validated knowledge. Inspect the real codebase to verify assumptions.

The implementation plan is non-normative. Never invent or change product behavior to make planning easier.

## Minimum-sufficient-plan principle

Prefer the smallest plan that gives clear ownership, dependency ordering, reviewable vertical progress, and adequate verification.

Do not create additional slices merely to isolate small implementation details that can safely be completed and reviewed together. Before decomposing the change, assess its actual implementation complexity and risk. A feature may legitimately need one implementation slice, a small number of sequential slices, or a larger vertical-slice graph only when its behavior and risk justify it. Do not assume every feature requires several slices or several high-risk slices.

Decomposition is justified by factors such as:

- independently meaningful end-to-end behaviors;
- substantial persistence or migration work;
- complex lifecycle or failure semantics;
- concurrency, deadline, cancellation, or security behavior;
- agent or tool boundaries;
- multiple independently risky integration surfaces; or
- changes that benefit materially from isolated implementation and review.

Small integration, configuration, UI, documentation, or conformance changes should usually have a much smaller plan.

Typical sizing examples:

- One slice: a narrow provider configuration addition with its validation, wiring, and focused tests.
- Two or three slices: a moderate endpoint feature split into a usable happy path, separately risky failure behavior, and integration conformance when those increments are independently reviewable.
- Larger graph: a durable agent workflow involving migrations, lifecycle/concurrency semantics, tool boundaries, and multiple external integrations whose risks need separate review.

## Behavioral vertical slicing

Plan from observable behavior and acceptance scenarios, not from folders, layers, or task numbering. For a multi-slice change, prefer an initial walking-skeleton slice that closes a real end-to-end path, then add coherent behavioral increments.

When decomposition is useful, prefer one usable behavior across contract -> implementation -> tests over separate contract, repository, service, and test slices. Separate technical layers only when doing so is necessary for dependency ordering or concrete risk control.

Each slice must:

- deliver one meaningful, reviewable increment;
- include the layers needed to make that behavior real rather than defer critical integration to a final catch-all slice;
- have explicit dependencies and focused verification;
- leave the repository valid when complete;
- fit comfortably in one fresh implementation context without relying on compaction;
- map back to exact OpenSpec requirements/scenarios/tasks.

Avoid horizontal plans such as "all models -> all repositories -> all algorithms -> integrate everything".

## Proportional risk classification

Classify every slice independently as `normal` or `high-risk` based on the semantics of that slice's actual delta. Use `high-risk` when the slice materially affects public or domain contracts, persistence or migrations, lifecycle or failure semantics, concurrency/deadline/cancellation, security or credentials, external transport semantics, dependencies, or architecture-sensitive integration.

Do not mark every slice high-risk because the overall feature contains one high-risk area. Preserve fresh independent review for the slices whose own deltas are genuinely high-risk.

## Verification proportionality

The plan should define intended scope, behavioral goal, dependencies, important boundaries and non-goals, verification strategy, and a completion gate. It should not normally prescribe custom checksum algorithms, source-byte reconstruction, AST or token inventory scripts, custom newline parsers, detailed shell algorithms, or redundant commit/digest tracking.

Put low-level audit mechanisms in implementation or review tooling only when a concrete risk cannot be adequately controlled with normal Git diff/history, focused tests, static checks, and independent review. Name that risk when such machinery is required.

If exact Git identity is needed, define one authoritative execution-anchor location. Elsewhere prefer named concepts such as `approved planning state`, `accepted previous slice`, and `current candidate tip`, with exact Git resolution recorded once in durable execution metadata. Do not scatter raw commit SHAs through slice descriptions and gates.

## Bounded corrections after approval

Bounded implementation corrections do not require a new slice graph when approved behavior, architecture/ADRs, public and domain contracts, slice ownership or dependency graph, schema, dependencies, and lifecycle/security/concurrency semantics all remain unchanged. They remain execution work inside a narrow approved boundary.

Require structural re-planning, independent plan review, and renewed human approval when a correction materially changes any of those boundaries. Do not pre-create speculative correction slices.

## Final conformance

Use one compact final conformance or review step when it adds value. It should verify the whole approved change and repository compatibility. Do not create multiple overlapping final verification slices that repeat the same checks unless distinct risks genuinely require them.

## Complexity sanity check

Before finalizing, ask:

- Is the execution/governance complexity materially larger than the implementation complexity? If yes, simplify unless a concrete risk justifies the additional complexity.
- Could two adjacent slices be safely combined while retaining clear behavioral ownership and reviewability? If yes, prefer the simpler graph.

## Required plan content

Write `openspec/changes/<change>/implementation-plan.md` using the project template. Include:

- change identity and approved-source references;
- dependency-ordered slices;
- for each slice: behavioral goal, OpenSpec coverage, ownership, dependencies, vertical boundary, expected code impact, contracts consumed/changed, non-goals, verification strategy, completion gate, context pack, handoff expectations, and `normal|high-risk` classification;
- a compact coverage matrix showing that every approved requirement/scenario/task has an owning slice and appropriate verification;
- frozen-plan vs mutable execution-state rules.

Default execution is sequential even if independent slices are identified.

## Blocking rule

If safe decomposition requires resolving a contradiction, unspecified behavior, Open/Deferred decision, missing dependency approval, or architecture gap, stop with:

`IMPLEMENTATION PLANNING BLOCKED`

Report the exact conflicting/insufficient sources, why planning cannot proceed safely, and the decision required. Do not resolve the gap yourself.

## Completion

Return either `PLAN READY FOR REVIEW` or `IMPLEMENTATION PLANNING BLOCKED`. A ready plan still requires independent plan review and explicit human approval before execution. Do not modify production code or mark the plan human-approved.
