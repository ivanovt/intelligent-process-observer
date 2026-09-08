## Context

See `proposal.md` for motivation and `specs/observation-management-ui/spec.md` for observable behavior.

Create Observation already renders five anchored aggregate sections and a sticky desktop navigation card. The links navigate correctly, but their presentation is static. The implementation must work with the current React/Tailwind stack, add no dependency, preserve native anchor behavior, and remain inert with respect to the Observation draft and API layer.

## Goals / Non-Goals

**Goals:**

- Keep one deterministic active section across initial render, link activation, manual scrolling, resizing, and the document bottom.
- Make the active state visible and programmatically discoverable.
- Keep scroll work proportional to the five fixed configuration sections.

**Non-Goals:**

- Turn the aggregate form into a step-by-step wizard or prevent non-linear navigation.
- Change URL routing, draft state, validation, nested editors, or submission.
- Add smooth-scroll behavior, animation infrastructure, or a third-party scrollspy dependency.
- Show the desktop configuration navigation at breakpoints where it is currently hidden.

## Decisions

### 1. Derive the active item from section geometry using one passive viewport listener

Maintain a local active-section identifier initialized to `general`. On scroll and resize, schedule at most one calculation per animation frame. The calculation inspects the five known section positions, selects the last section whose leading edge has crossed a stable activation line near the upper part of the viewport, and falls back to `general` before the first section crosses it. When the document bottom is reached, it selects `review` explicitly so a short final section is not skipped.

This is preferred over a new dependency because five `getBoundingClientRect` reads are bounded and simple. It is preferred over a narrow `IntersectionObserver` band because section-height differences and viewport changes can leave no observed section intersecting the band, while the positional rule always produces one result.

### 2. Treat click selection as immediate feedback while retaining native anchors

Each existing anchor sets the same local active identifier in its click handler and retains its `href`. Native fragment navigation therefore continues to perform scrolling and keyboard activation without a custom scrolling implementation. The next geometry calculation reconciles the state with the actual viewport.

### 3. Use a semantic current-location marker and token-based visual treatment

The active link exposes `aria-current="location"` and receives a restrained primary-tinted background, primary text, and stronger weight. Inactive links retain the existing hover and focus behavior. Exactly one link receives the marker.

## Risks / Trade-offs

- **[Risk] Browser rounding near a section boundary could cause rapid changes.** → Use one stable activation line and a last-crossed-section rule rather than competing intersection ratios.
- **[Risk] The short Review section may never cross the activation line.** → Select Review explicitly at the document bottom.
- **[Risk] Scroll events could cause excessive renders.** → Use a passive listener, animation-frame coalescing, and retain the current state when the computed identifier has not changed.
- **[Risk] Tests run without real layout.** → Mock section geometry, viewport position, and animation-frame scheduling in focused component tests while retaining existing aggregate-flow regressions.

## Migration Plan

Add the local scrollspy behavior and focused tests, then run the complete frontend suite and `make check`. Rollback is a normal revert of the frontend and delta-spec changes; no data migration or API coordination is required.

## Architecture References

- `docs/architecture/`: N/A — active-section feedback does not alter domain or runtime semantics.
- `docs/ui/ui_implementation_handoff_v1.md`: preserves the five accepted aggregate configuration sections and their non-linear draft workflow.
- `docs/ui/frontend_ui_stack_adr.md`: uses existing React, Tailwind CSS, and project-owned UI code without a dependency change.
