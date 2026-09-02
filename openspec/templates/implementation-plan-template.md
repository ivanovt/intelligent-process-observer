# Implementation Plan — <change-name>

**Status:** DRAFT | REVIEWED | HUMAN_APPROVED | IN_PROGRESS | COMPLETE | BLOCKED
**Artifact type:** Non-normative execution plan
**Approved OpenSpec change:** `<change-name>`
**Candidate branch:** `<branch>`

## Authority and constraints

This file describes how the approved change will be implemented. It does not redefine what must be implemented. Accepted ADRs/normative contracts and the approved OpenSpec remain authoritative.

After human approval, slice structure is frozen. Only the Coordinator may update execution metadata. Structural changes require re-planning, independent plan review, and human re-approval.

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

**Expected code impact:** modules/boundaries ...

**Contracts consumed/changed:** ...

**Non-goals:** ...

**Focused verification:** ...

**Context pack:** exact docs/ADRs/spec sections/code areas to read ...

**Handoff expectations:** ...

**Risk:** normal | high-risk

**Completion gate:** ...

## Coverage matrix

| OpenSpec requirement/scenario/task | Owning slice | Verification |
|---|---|---|
| ... | VS-01 | ... |

## Execution notes

Mutable Coordinator-owned execution metadata only. Do not place new requirements or redesign decisions here.
