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

## Required plan content

Write `openspec/changes/<change>/implementation-plan.md` using the project template. Include:
- change identity and approved-source references;
- dependency-ordered slices;
- for each slice: behavioral goal, OpenSpec coverage, dependencies, vertical boundary, expected code impact, contracts consumed/changed, non-goals, focused verification, context pack, handoff expectations, `normal|high-risk`;
- a coverage matrix proving every approved requirement/scenario/task has an owning slice and appropriate verification;
- frozen-plan vs mutable execution-state rules.

Default execution is sequential even if independent slices are identified.

## Blocking rule

If safe decomposition requires resolving a contradiction, unspecified behavior, Open/Deferred decision, missing dependency approval, or architecture gap, stop with:

`IMPLEMENTATION PLANNING BLOCKED`

Report the exact conflicting/insufficient sources, why planning cannot proceed safely, and the decision required. Do not resolve the gap yourself.

## Completion

Return either `PLAN READY FOR REVIEW` or `IMPLEMENTATION PLANNING BLOCKED`. Do not modify production code or mark the plan human-approved.
