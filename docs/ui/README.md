# UI Documentation

This directory contains the frozen UI direction, frontend technology decision, and implementation guidance for the MVP frontend.

## Files

- `frontend_ui_stack_adr.md` — accepted frontend visual technology stack and related trade-offs.
- `ui_implementation_handoff_v1.md` — frozen implementation-oriented UI specification covering monitoring/investigation and Observation Management UX.

## Status

**UI Direction v1.2 is frozen.**

v1.1 extended the original monitoring/investigation direction with Observation Management:

```text
09 Observations Management
10 Create Observation
11 Relationship Configuration
12 Metric Lens Configuration
13 Alert Lens Configuration
```

v1.2 retains that screen set and replaces manual Metric Lens, Alert Lens, and
Relationship ID entry with generated, read-only IDs derived once from the initial
name and then kept stable.

The implementation must preserve accepted information architecture, terminology, analytical/execution semantics, aggregate ownership, Lens configuration boundaries, and evidence/knowledge boundaries.

Minor implementation adjustments are allowed for responsive fit, accessibility, browser behavior, real data length, and actual API constraints. Meaningful visual, UX, or semantic changes require an explicit UI version change.

## Source of truth

Frozen MagicPath visual reference:

```text
Observation UI - Master Thesis
https://magicpath.ai/files/447597481925181440
```

Accepted domain/runtime contracts under `docs/architecture/` remain authoritative for backend/domain semantics.

## Usage

Before planning, implementing, or reviewing a frontend change, read:

1. `frontend_ui_stack_adr.md`
2. `ui_implementation_handoff_v1.md`
3. relevant architecture/contracts under `docs/architecture/`

For Observation Management, preserve the draft/aggregate workflow: nested Metric Lens, Alert Lens, and Relationship editors apply changes to the Observation draft; only the final `Create Observation` action submits the validated aggregate.
