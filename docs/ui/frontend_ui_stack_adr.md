# ADR — Frontend UI Technology Stack for MVP

**Status:** Accepted
**Date:** 2026-09-07

## Context

UI Direction v1.2 is frozen. The frontend needs a visual implementation stack that preserves the project-owned visual/domain language, supports desktop-first engineering dashboards and forms, and remains mainstream and maintainable.

## Decision

The MVP frontend visual stack is fixed as:

```text
React
Tailwind CSS 4
shadcn/ui
Base UI primitives
Lucide React
Recharts
TanStack Table — only where advanced tabular behavior is required
```

Project-owned semantic design tokens use CSS custom properties integrated with Tailwind.

Third-party primitives do not own ObserveAI domain semantics. Project-owned components encapsulate analytical state, execution state, Lens configuration, findings/hypotheses, and traceability concepts.

Observation Management UX introduced in UI Direction v1.1 uses the same stack and does not introduce a separate admin design system.

## Tables

TanStack Table is optional and should be used only when advanced sorting/filtering/pagination/column behavior is needed. Simple dashboard and Observation-management lists should remain lightweight project-owned components unless real requirements justify a table abstraction.

## Charts

Recharts is the default MVP visualization library for Metric time-series, simple comparisons/history, and run-activity charts. It remains replaceable behind project-owned chart components if future high-density engineering visualization requires a different engine.

## Alternatives considered

- Material UI — not selected because the project already owns a distinct visual language and would require substantial visual overrides.
- Fully custom primitives — not selected because mature headless primitives already solve interaction/accessibility concerns.
- Apache ECharts — retained as a future alternative for denser/more specialized visualization, not needed for current MVP requirements.

## Consequences

Positive:

- full control over the frozen ObserveAI visual direction;
- mainstream React ecosystem;
- reusable accessible primitives;
- semantic design tokens and project-owned domain components;
- chart/table libraries remain independently replaceable.

Trade-offs:

- generated shadcn components remain project-owned and require maintenance;
- consistent component discipline is required to avoid arbitrary one-off Tailwind styling;
- Recharts may be insufficient for future high-density engineering datasets;
- TanStack Table adds complexity and should not be used by default.

## Scope

This decision fixes the MVP frontend visual implementation stack. It does not yet fix routing, global client-state management, data-fetching/cache strategy, forms library, test stack, dark mode, or final responsive breakpoint details.

## Implementation rule

**UI Direction v1.2 is the frozen visual/UX source of truth.**

Third-party libraries must adapt to the design; the design must not be rewritten to match library defaults. Domain semantics and backend lifecycle ownership remain governed by accepted architecture/contracts.
