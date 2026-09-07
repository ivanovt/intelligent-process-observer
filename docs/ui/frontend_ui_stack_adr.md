# ADR — Frontend UI Technology Stack for MVP

**Status:** Accepted
**Date:** 2026-09-07

## Context

UI Direction v1.0 is frozen. The frontend now needs a visual implementation stack that:

- preserves the project-owned visual language instead of imposing a vendor design system;
- supports desktop-first engineering dashboards;
- supports reusable semantic components such as analytical-state badges, execution-state badges, Lens cards, Finding/Hypothesis cards, and traceability chips;
- supports charts for Metric Lens views;
- supports richer tables where sorting/filtering/pagination are actually needed;
- remains mainstream, maintainable, and suitable for implementation by coding agents;
- keeps domain semantics owned by the project rather than by third-party UI libraries.

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

### Styling and design tokens

Project-owned semantic design tokens will be implemented with:

```text
CSS custom properties
+
Tailwind theme integration
```

The UI must avoid scattering raw visual values when those values have domain meaning.

Examples of project-owned semantic tokens:

```text
--background
--surface
--surface-muted
--border
--text-primary
--text-secondary

--state-no-findings
--state-uncertain
--state-significant

--execution-completed
--execution-partial
--execution-failed

--evidence
--relationship
--knowledge
```

### Project-owned semantic components

Third-party libraries provide primitives and behavior, but the following remain project-owned UI components:

```text
AppShell
PageHeader
SummaryCard
ObservationRow
RecentRunsStrip

AnalyticalStateBadge
ExecutionStatusBadge

LensCard
FindingCard
HypothesisCard

EvidenceChip
RelationshipChip
KnowledgeChip
```

The exact list may grow during implementation, but domain semantics must remain encapsulated in project components.

### Tables

TanStack Table is not a mandatory dependency for every list.

Use it only when advanced table behavior is needed, such as:

```text
sorting
filtering
pagination
column visibility
row selection
large tabular datasets
```

Simple Overview lists/rows should remain project-owned layout components.

### Charts

Recharts is the default MVP visualization library for:

```text
metric time-series
reference comparisons
recent-run/history visualizations
run activity charts
```

A future switch to a more specialized visualization engine is allowed if real requirements such as very large datasets, advanced zooming, heatmaps, or high-density engineering visualization emerge.

## Alternatives considered

### Material UI

Not selected as the default frontend component system because the project already has a distinct visual language and would otherwise require substantial styling overrides of Material conventions.

### Fully custom CSS/components

Not selected because it would duplicate accessibility and interaction behavior already provided by mature headless primitives.

### Apache ECharts

Kept as a future visualization alternative for higher-density or more specialized engineering charts, but not selected for the MVP because the current visualization requirements are relatively conventional.

## Consequences

### Positive

- high control over the frozen ObserveAI visual direction;
- mainstream React ecosystem;
- reusable accessible primitives without adopting a foreign visual language;
- coding agents can work with familiar declarative component patterns;
- semantic state remains explicit in project-owned components;
- design tokens can map directly from the frozen Design System;
- visualization and table libraries can evolve independently from the rest of the UI.

### Trade-offs

- shadcn/ui components are project-owned copies, so maintenance remains our responsibility;
- a consistent component layer must be enforced to avoid arbitrary Tailwind styling across screens;
- Recharts may eventually be insufficient for very large or highly interactive engineering datasets;
- TanStack Table adds complexity and must not be introduced where a simpler layout is sufficient.

## Scope

This decision fixes the MVP frontend visual implementation stack.

It does **not** yet define:

- exact component folder structure;
- exact token names/values beyond the semantic direction;
- exact responsive breakpoints;
- frontend state-management strategy;
- data-fetching/cache strategy;
- router choice;
- form-state library;
- testing-library choices;
- final chart interaction behavior;
- dark-mode support.

Those remain separate implementation decisions.

## Implementation rule

The frozen UI Direction v1.0 remains the visual source of truth.

Third-party libraries must adapt to the design; the design must not be rewritten to match library defaults.

Analytical state, execution state, evidence, relationships, and knowledge references must remain separate semantic concepts in the UI.
