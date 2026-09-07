# UI Documentation

This directory contains the frozen UI direction and implementation guidance for the MVP frontend.

## Files

- `frontend_ui_stack_adr.md` — accepted frontend visual technology stack and related trade-offs.
- `ui_implementation_handoff_v1.md` — implementation-oriented UI specification, including screen contracts, semantic rules, design tokens, reusable components, and library usage guidance.

## Status

**UI Direction v1.0 is frozen.**

The current implementation should preserve the accepted information architecture, terminology, analytical/execution-state semantics, and evidence/knowledge boundaries.

Minor implementation adjustments are allowed for technical reasons such as responsive fit, accessibility, browser behavior, and real data length. Meaningful visual or semantic changes should be handled explicitly as a new UI version rather than introduced silently during implementation.

## Source of truth

The visual reference is the frozen MagicPath design.

The Markdown files in this directory are the implementation handoff and decision record used by planning, implementation, and review agents.

## Usage

Before planning or implementing a frontend change, read:

1. `frontend_ui_stack_adr.md`
2. `ui_implementation_handoff_v1.md`
3. the relevant architecture/contracts under `docs/architecture/`

Frontend features should be implemented incrementally and reuse the project-owned semantic component layer rather than introducing one-off styling or new domain semantics.
