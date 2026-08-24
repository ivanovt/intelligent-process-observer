# Development Workflow — Quick Guide

This document is the short, repeatable workflow for implementing changes in **Intelligent Process Observer**. It is intended for both existing contributors and people joining the project for the first time.

For environment setup and detailed repository conventions, see [`development-guide.md`](development-guide.md). For agent governance, always read the root [`AGENTS.md`](../AGENTS.md).

## 1. Mental model

The project separates four concerns:

```text
Architecture / ADRs
    ↓ constrain
OpenSpec change
    ↓ defines
Implementation
    ↓ verified by
Tests + independent review
```

- `docs/architecture/` is authoritative for architecture, contracts, ADRs, and open/deferred decisions.
- `openspec/changes/<change-id>/` defines the currently proposed/implemented behavioral change.
- `openspec/specs/` contains accepted behavior from archived changes.
- code implements the approved architecture and specifications.

Never silently resolve an architecture item marked `Open` or `Deferred`.

## 2. Decide whether OpenSpec is required

Use a **direct change** for small, mechanical work whose behavior is already completely defined, such as documentation, formatting, an obvious local bug fix, or a behavior-preserving refactor.

Use an **OpenSpec change** for new or changed behavior, contracts, lifecycle/failure semantics, database meaning, agents/tools, cross-module interaction, or new acceptance criteria.

When uncertain, ask before implementing.

## 3. Standard OpenSpec feature workflow

```text
feature/<change-id>
      ↓
explore (optional)
      ↓
propose
      ↓
ipo-review-plan
      ↓
human approval
      ↓
apply
      ↓
make check
      ↓
openspec-verify-change
      ↓
ipo-review-implementation
      ↓
human triage + targeted fixes
      ↓
ipo-verify-findings
      ↓
archive in feature branch
      ↓
final diff + make check
      ↓
PR + CI + review
      ↓
squash merge to main
```

The human approval step before implementation is mandatory.

## 4. Create the feature branch

Start from up-to-date `main`:

```bash
git switch main
git pull --ff-only
git switch -c feature/<change-id>
```

Normally use the same kebab-case identifier for the OpenSpec change and branch.

## 5. Explore when the feature still contains real unknowns

Use OpenSpec exploration when you do not yet know what should be built or when architecture decisions must be surfaced first.

Codex example:

```text
$openspec-explore <topic>
```

Exploration is not implementation. If it discovers a missing architecture decision, stop and resolve that decision explicitly before turning it into a spec.

## 6. Propose the change

Create the planning artifacts:

```text
$openspec-propose <change description>
```

Expected artifacts normally include:

```text
openspec/changes/<change-id>/
├── proposal.md
├── specs/.../spec.md
├── design.md        # when needed
└── tasks.md
```

All project-facing OpenSpec artifacts are written in English.

## 7. Review the plan before code exists

Run the project-specific planning review:

```text
$ipo-review-plan <change-id>
```

This skill is **report-only**. It checks proposal/spec/design/tasks against:

- `AGENTS.md`;
- architecture and ADR precedence;
- referenced contracts;
- Open/Deferred decisions;
- scope boundaries;
- requirement/scenario quality;
- design ownership boundaries;
- task/test completeness.

Possible final results:

```text
READY FOR HUMAN APPROVAL
READY WITH MINOR CORRECTIONS
CHANGES REQUIRED
ARCHITECTURE DECISION REQUIRED
```

Correct the planning artifacts until the plan is acceptable. Then obtain explicit human approval before apply.

## 8. Implement the approved change

Use the OpenSpec apply workflow:

```text
$openspec-apply-change <change-id>
```

During implementation:

- follow the approved artifacts exactly;
- do not change architecture or scope silently;
- stop if implementation reveals a missing decision;
- keep code documentation aligned with the rules in `AGENTS.md`;
- add tests that prove behavior, not only happy-path execution.

Before review:

```bash
make check
```

## 9. Run OpenSpec's standard implementation verification

The project recommends enabling the optional official OpenSpec verify workflow.

Invoke it before the project-specific implementation review:

```text
$openspec-verify-change <change-id>
```

OpenSpec verify checks whether the implementation matches the change artifacts across completeness, correctness, and coherence. It is report-only and does not replace the project-specific architecture review.

Reference: https://openspec.dev/docs/skills

### Enable the official verify workflow

If `openspec-verify-change` is not installed:

```bash
openspec config profile
```

Keep the core workflows selected and also enable `verify`, then apply the profile to the project or run:

```bash
openspec update
```

Commit the generated OpenSpec integration files. OpenSpec documents `verify` as an optional workflow outside the default core set.

Reference: https://openspec.dev/docs/profiles

Do not hand-edit generated `openspec-*` skills; keep project-specific custom skills under the `ipo-*` namespace.

## 10. Run the independent project implementation review

Prefer a **fresh Codex/reviewer session** for this step.

Invoke:

```text
$ipo-review-implementation <change-id>
```

This skill is **report-only**. It reviews:

- approved OpenSpec requirements/scenarios;
- architecture/ADR compliance;
- `git diff` against `main`;
- lifecycle/failure/identity/cardinality semantics;
- persistence and migration integrity when applicable;
- real integration-test quality;
- scope creep and unnecessary complexity;
- code documentation quality.

Findings use:

```text
BLOCKER
HIGH
MEDIUM
LOW
```

Final assessment:

```text
READY
READY WITH MINOR FIXES
CHANGES REQUIRED
```

Do not ask the reviewer to fix its own findings in the same pass.

## 11. Triage findings and apply targeted fixes

The human/reviewer owner decides which findings are valid.

Return only accepted findings to the implementation session, for example:

```text
Fix IR-001, IR-002 and IR-004.
IR-003 was reviewed and rejected.
Do not make unrelated refactors.
```

After fixes, run focused tests and `make check` as appropriate.

## 12. Verify only the known findings

Use the bounded follow-up skill instead of restarting a full review loop:

```text
$ipo-verify-findings <change-id> IR-001 IR-002 IR-004
```

The finding descriptions must be available in the session or supplied as a report/text. If a fresh session only has IDs, provide the previous review output as context.

Possible statuses:

```text
RESOLVED
PARTIALLY RESOLVED
NOT RESOLVED
WITHDRAWN
```

`WITHDRAWN` is appropriate when exact normative architecture/spec evidence proves the original review finding was incorrect.

The skill also checks for fix-induced regressions and ends with:

```text
READY FOR ARCHIVE
NOT READY FOR ARCHIVE
```

A change is archive-ready only when no unresolved BLOCKER/HIGH/MEDIUM finding or new regression remains.

## 13. Archive only after implementation review converges

When the change is ready:

```text
$openspec-archive-change <change-id>
```

This repository archives **inside the feature branch before the PR**. Review the generated canonical `openspec/specs/` changes and archived change folder.

Then run:

```bash
make check
git diff main...HEAD
```

Archive does not replace final human sanity review.

## 14. Pull request and merge

Open a PR to protected `main` only after archive and local verification.

The PR should include:

- summary;
- OpenSpec change id;
- architecture references;
- reviewer notes and noteworthy implementation decisions;
- verification status.

Required CI must pass. Use squash merge.

Agents require explicit user approval before push, PR creation/update, merge, direct `main` changes, or remote-history rewriting.

## 15. Skill reference

| Skill | When | Modifies files? | Purpose |
| --- | --- | --- | --- |
| `$openspec-explore` | Before propose when requirements are unclear | Normally no | Clarify the problem and surface decisions. |
| `$openspec-propose` | Start a behavioral change | Yes, planning artifacts | Create proposal/spec/design/tasks. |
| `$ipo-review-plan` | After propose, before approval | **No** | Independent architecture/spec plan review. |
| `$openspec-apply-change` | After explicit approval | Yes | Implement approved tasks. |
| `$openspec-verify-change` | After implementation | **No** | Official OpenSpec plan-vs-code verification. |
| `$ipo-review-implementation` | After apply/check, before archive | **No** | Project-specific architecture/code/test review. |
| `$ipo-verify-findings` | After targeted fixes | **No** | Verify known findings and regressions only. |
| `$openspec-archive-change` | After review converges | Yes, OpenSpec artifacts | Sync canonical specs and archive the change. |

OpenSpec's current documentation describes `verify` as optional and report-only, and recommends review before apply and verification after implementation.

Reference: https://openspec.dev/docs/reviewing-changes

## 16. Review-loop rule of thumb

Do not let review become an endless redesign loop.

Use this sequence:

```text
broad plan review
→ implement
→ broad implementation review
→ human triage
→ targeted fixes
→ targeted finding verification
→ archive
```

If a finding reveals a genuine missing architecture decision, stop implementation and resolve the architecture first. If a finding is contradicted by the normative architecture, withdraw it rather than changing valid code to satisfy the reviewer.

## 17. Where the custom skills live

Project-maintained skills live under:

```text
.agents/skills/ipo-review-plan/SKILL.md
.agents/skills/ipo-review-implementation/SKILL.md
.agents/skills/ipo-verify-findings/SKILL.md
```

The `ipo-*` namespace separates repository-owned skills from OpenSpec-generated `openspec-*` skills, which may be regenerated by `openspec update`.

Custom skills should evolve only after repeated real workflow evidence. Avoid creating speculative one-off skills.
