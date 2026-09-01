---
name: ipo-implementation-planner
description: >-
  Create a non-normative vertical-slice implementation plan for an already approved OpenSpec change. Use before coding a large or complex approved change to map requirements, scenarios, and tasks into dependency-ordered slices sized for fresh contexts; stop on source conflicts or unresolved decisions.
---

# IPO Implementation Planner

## Purpose

Convert one already-approved OpenSpec change into a compact, executable vertical-slice plan. Optimize for correctness, early integration, and fresh-context implementation. Do not implement production code.

## Source of truth

Read repository governance first, then the complete approved OpenSpec change and all referenced accepted ADRs / normative architecture and contracts. Read `.agents/PROJECT_KNOWLEDGE.md` as advisory validated knowledge. Inspect the real codebase to verify assumptions.

The implementation plan is non-normative. Never invent or change product behavior to make planning easier.

## Planning method

Plan from observable behavior and acceptance scenarios, not from folders, layers, or task numbering. Prefer a walking-skeleton slice that closes a real end-to-end path early, then add coherent behavioral increments.

Each slice must:
- deliver one meaningful observable increment;
- include the layers needed to make that behavior real rather than defer critical integration to a final catch-all slice;
- have explicit dependencies and focused verification;
- leave the repository valid when complete;
- fit comfortably in one fresh implementation context without relying on compaction;
- map back to exact OpenSpec requirements/scenarios/tasks.

Avoid horizontal plans such as "all models -> all repositories -> all algorithms -> integrate everything".

## Slice proof design

Translate approved normative behavior into slice-local proof obligations; do not create
new product acceptance criteria. A valid behavioral source is an approved OpenSpec
requirement clause/scenario or an accepted normative ADR/contract clause. OpenSpec tasks
may appear as supplementary traceability but must not be the sole source of a behavioral
acceptance obligation. Process-only tasks such as documentation audits, validation,
formatting, full-suite execution, commits, reviews, or handoffs belong in completion
gates, not acceptance IDs. If an approved behavioral task cannot be traced to normative
behavior, apply the blocking rule rather than turning the task into a requirement.

Approved design/task constraints that govern implementation technique without defining
normative observable behavior—such as internal strict-model strategy, framework retry
configuration, or code-quality checks—belong in a separately labeled technical
verification list and the completion gate. They do not receive acceptance IDs.

Give every obligation a stable ID scoped to its slice, for example `VS02-AC03`. Each
obligation must identify:

- the exact approved normative source clause/scenario, with tasks only as supplementary
  traceability;
- a discriminating GIVEN fixture or precondition;
- the action or boundary being exercised;
- the exact observable result, including important absence or non-mutation assertions;
- the required proof level (`unit`, `service`, `ASGI`, real PostgreSQL, migration,
  framework adapter, or another concrete boundary);
- a full runnable test node/command for every claimed proof level; and
- when useful, a plausible incorrect implementation that the proof must detect.

Proof obligations must be implementation-ready and falsifiable. Avoid obligations that
only say a path is covered, a test exists, or a suite passes. Use adversarial fixtures
when ordinary fixtures could let an incorrect ordering, transaction, validation, or
boundary implementation pass.

Keep the completion gate separate from behavioral proof. It should reference the
slice's acceptance IDs and contain only repository/process conditions such as focused
technical/design checks, regression checks, scope audit, required review verdict, atomic
implementation commit, and handoff.

After human approval, acceptance ID, approved source, GIVEN/WHEN/THEN assertions, proof
level, planned counterexample guards, and slice ownership are structural plan content.
Adding, removing, merging, renumbering, or changing any of them requires re-planning,
independent plan review, and human re-approval. Only execution evidence/results against
the frozen obligation are mutable metadata.

## Implementation guidance

Replace broad file-area predictions with a concrete change map naming expected paths or
symbols, whether they are added or modified, and their responsibility in the slice.
Treat the map as a grounded implementation forecast, not a frozen internal API: the
implementer may report a local naming/path adjustment in the handoff when behavior and
boundaries remain unchanged.

Add a short implementation sketch only when it materially clarifies a high-risk or
otherwise ambiguous seam such as an interface shape, orchestration order, transaction
boundary, state transition, adapter translation, algorithm, or migration sequence.
Sketches are illustrative and non-normative, must be derived from approved sources and
real code, and should normally fit within 5-25 lines. Do not pre-write routine production
code or add a sketch merely to fill the section. If a useful sketch would require
inventing behavior, apply the blocking rule instead.

Keep each context pack bounded to the exact normative sections, code areas, direct
dependency handoffs, and inherited invariants needed by that slice. Do not require all
predecessor handoffs, the complete change, broad ADR ranges, or all changed code/tests
when targeted sources suffice.

## Required plan content

Write `openspec/changes/<change>/implementation-plan.md` using the project template. Include:
- change identity and approved-source references;
- dependency-ordered slices;
- for each slice: behavioral goal, OpenSpec coverage, dependencies, vertical boundary,
  concrete change map, contracts consumed/changed, non-goals, acceptance-evidence table,
  technical verification for approved non-normative design/task constraints when needed,
  optional bounded implementation sketch where justified, focused verification commands,
  context pack, handoff expectations, `normal|high-risk`, and a process-only completion
  gate referencing every slice acceptance ID;
- a coverage matrix proving every approved requirement/scenario/task has an owning slice and appropriate verification;
- frozen-plan vs mutable execution-state rules.

Keep requirements in the OpenSpec rather than duplicating their prose into the plan.
The acceptance-evidence tables explain how slices prove those requirements; the coverage
matrix proves ownership across the complete change.

Default execution is sequential even if independent slices are identified.
High-risk slice completion requires the final independent verdict `SLICE REVIEW PASS`;
the absence of selected severity labels is not a substitute for that verdict.

## Blocking rule

If safe decomposition requires resolving a contradiction, unspecified behavior, Open/Deferred decision, missing dependency approval, or architecture gap, stop with:

`IMPLEMENTATION PLANNING BLOCKED`

Report the exact conflicting/insufficient sources, why planning cannot proceed safely, and the decision required. Do not resolve the gap yourself.

## Completion

Return either `PLAN READY FOR REVIEW` or `IMPLEMENTATION PLANNING BLOCKED`. Do not modify production code or mark the plan human-approved.
