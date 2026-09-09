# UI Documentation

This directory contains the accepted current UI direction, frontend technology decision, and implementation guidance for the MVP frontend.

## Files

- `frontend_ui_stack_adr.md` — accepted frontend visual technology stack and related trade-offs.
- `ui_implementation_handoff_v1.md` — living major-v1 implementation handoff (currently v1.4) covering monitoring/investigation, run management, Observation Management, and Data Sources UX.

## Status

**UI Direction v1.4 is the accepted current direction.**

v1.2 retained the monitoring/investigation and Observation Management direction, and added:

```text
09 Observations Management
10 Create Observation
11 Relationship Configuration
12 Metric Lens Configuration
13 Alert Lens Configuration
14 Data Sources
```

v1.3 retains that screen set and replaces manual Metric Lens, Alert Lens, and
Relationship ID entry with generated, read-only IDs derived once from the initial
name and then kept stable.

v1.4 adds the global Runs history/launch screen and operationalizes the existing
Observation Run Summary as a routable detail foundation. It keeps execution status
independent from analytical state, uses a single-process on-demand launch boundary,
requires Copy Markdown but defers report export, and treats detailed visual refinement
as a later versioned change.

The implementation must preserve accepted information architecture, terminology, analytical/execution semantics, aggregate ownership, Lens configuration boundaries, and evidence/knowledge boundaries.

Minor implementation adjustments are allowed for responsive fit, accessibility, browser behavior, real data length, and actual API constraints. Meaningful visual, UX, or semantic changes require an explicit UI version change.

## Authority and visual reference

ADR-167 defines the authority order for UI work:

1. accepted domain/runtime architecture and public contracts govern product semantics and API boundaries;
2. accepted `docs/ui/` direction/handoff plus approved OpenSpec changes govern UI behavior, information architecture, and intentional visual evolution;
3. MagicPath is an informative visual reference and optional synchronization target, not a parity requirement or implementation/acceptance gate;
4. meaningful UI changes remain versioned and human-approved.

Informative MagicPath visual reference:

```text
Observation UI - Master Thesis
https://magicpath.ai/files/447597481925181440
```

MagicPath can guide look and feel, but an approved change does not require 1:1 canvas parity or synchronization. Historical v1.1 through v1.3 wording remains historical; ADR-167 and this current v1.4 documentation govern new work.

## Usage

Before planning, implementing, or reviewing a frontend change, read:

1. `frontend_ui_stack_adr.md`
2. `ui_implementation_handoff_v1.md`
3. relevant architecture/contracts under `docs/architecture/`

For Observation Management, preserve the draft/aggregate workflow: nested Metric Lens, Alert Lens, and Relationship editors apply changes to the Observation draft; only the final `Create Observation` action submits the validated aggregate.
