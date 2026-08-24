---
name: ipo-review-plan
description: Review an OpenSpec change plan against Intelligent Process Observer architecture, ADRs, repository governance, and internal artifact consistency before human approval and implementation.
argument-hint: "[change-id]"
---

# IPO Review Plan

Perform an independent, report-only review of an OpenSpec change before implementation begins.

Use this skill after `openspec-propose` or an approved planning-artifact update and before `openspec-apply-change`.

## Guardrails

- Do not modify files.
- Do not implement code.
- Do not edit OpenSpec artifacts, architecture documents, ADRs, or source code.
- Do not silently resolve `Open` or `Deferred` architecture decisions.
- Do not propose dependencies as accepted choices; dependency changes require explicit user approval.
- Treat `docs/architecture/` and accepted ADRs as normative according to `AGENTS.md` precedence rules.
- Treat the active OpenSpec change as the proposed behavioral contract, not as automatically correct.

## Input and change selection

Use `$ARGUMENTS` as the change id when supplied.

If no change id is supplied:

1. infer it from the current branch or conversation only when unambiguous;
2. otherwise inspect active changes with `openspec list --json`;
3. if more than one plausible change exists, ask the user to select one.

Always state which change is being reviewed.

## Review procedure

### 1. Load repository governance

Read:

1. root `AGENTS.md`;
2. `docs/architecture/README.md`;
3. the active change artifacts.

Read the OpenSpec artifacts in this order:

1. `proposal.md`;
2. all delta `spec.md` files;
3. `design.md` when present;
4. `tasks.md`.

### 2. Resolve architecture context

Inspect the `Architecture References` declared by proposal/design artifacts.

For each referenced file or ADR:

- confirm it exists;
- read the relevant section;
- verify that the OpenSpec artifacts reflect it accurately;
- apply architecture precedence from `AGENTS.md` when documents differ.

Also inspect `docs/architecture/10_open_decisions_and_backlog.md` when the change may depend on unresolved decisions.

Do not require the entire architecture package to be loaded when only a bounded subset is relevant.

### 3. Validate OpenSpec structure

Run strict OpenSpec validation for the change when the CLI/environment permits it.

Structural validation is supporting evidence only; it does not replace semantic review.

### 4. Review the proposal

Check:

- the problem and motivation match the intended feature;
- the scope is one coherent change;
- explicit out-of-scope boundaries are sufficient;
- no unrelated future capability is pulled in;
- architecture references are relevant and complete enough;
- no `Open` or `Deferred` item was converted into an implicit requirement;
- no architecture change is hidden as an implementation detail.

### 5. Review the specs

Check every requirement and scenario for:

- observable behavior rather than implementation detail;
- unambiguous SHALL-level semantics;
- lifecycle, failure, partial-result, absence, identity, and cardinality behavior when relevant;
- positive, negative, and boundary scenarios sufficient to expose the behavior;
- consistent terminology with architecture/glossary;
- no invented defaults, budgets, schemas, states, or provider behavior;
- no accidental generalization across type-specific contracts.

Call out requirements that cannot be implemented without an unresolved architectural decision.

### 6. Review the design

Check:

- the design actually implements the spec rather than changing it;
- choices remain inside the approved technology stack;
- architecture boundaries and ownership are preserved;
- persistence, orchestration, analytical, provider, agent, and presentation responsibilities are not blurred;
- rejected alternatives and trade-offs are reasonable for the MVP;
- the design does not create a second source of truth or premature abstraction;
- implementation details do not silently redefine domain contracts;
- any new dependency, framework, or architecture decision is surfaced for explicit approval.

### 7. Review the tasks

Check:

- tasks cover every requirement and important scenario;
- implementation order is coherent;
- tests and verification are explicit;
- migration/integration coverage is included when persistence behavior changes;
- documentation updates are included when non-trivial public code or developer workflow changes;
- `make check` is the final local verification step;
- tasks do not include out-of-scope work.

## Finding severity

Use only these severities:

- `BLOCKER` — the plan cannot be safely approved without an architecture/user decision, or it contradicts a normative contract in a fundamental way;
- `HIGH` — likely to produce incorrect behavior, broken contract semantics, or significant scope error;
- `MEDIUM` — meaningful ambiguity, missing scenario, test/design gap, or maintainability issue that should be corrected before implementation;
- `LOW` — minor clarity, documentation, naming, or local consistency improvement that does not change correctness.

Do not report stylistic preferences as findings.

## Output format

Return a report only.

For every finding use:

```text
ID: PR-001
Severity: BLOCKER | HIGH | MEDIUM | LOW
Artifact: proposal.md | spec path | design.md | tasks.md
Architecture/Requirement Reference:
Problem:
Why it matters:
Suggested direction:
```

Then provide:

```text
## Artifact assessment
Proposal: READY | NEEDS CHANGES
Specs: READY | NEEDS CHANGES
Design: READY | NEEDS CHANGES | N/A
Tasks: READY | NEEDS CHANGES

## Open architectural decisions
- None
or
- <decision that requires explicit human/ADR resolution>

## Scope risks
- None
or
- <risk>

## Final assessment
READY FOR HUMAN APPROVAL
| READY WITH MINOR CORRECTIONS
| CHANGES REQUIRED
| ARCHITECTURE DECISION REQUIRED
```

`READY FOR HUMAN APPROVAL` means no unresolved BLOCKER/HIGH/MEDIUM finding remains. Human approval is still mandatory before apply.
