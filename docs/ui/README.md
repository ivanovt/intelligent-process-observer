# UI Documentation

This directory contains the accepted current UI direction, frontend technology decision, and implementation guidance for the MVP frontend.

## Files

- `frontend_ui_stack_adr.md` — accepted frontend visual technology stack and related trade-offs.
- `ui_implementation_handoff_v1.md` — living major-v1 implementation handoff (currently v1.8) covering monitoring/investigation, run management, Observation Management, and Data Sources UX.

## Status

**UI Direction v1.8 is the accepted current direction.**

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
Relationship ID entry with generated identities derived once from the initial name and
then kept stable.

v1.4 adds the global Runs history/launch screen and operationalizes the existing
Observation Run Summary as a routable detail foundation. It keeps execution status
independent from analytical state, uses a single-process on-demand launch boundary,
requires Copy Markdown but defers report export, and treats detailed visual refinement
as a later versioned change.

v1.5 refines only the UI-generated identity of new Metric Lenses, Alert Lenses, and
Relationships. New IDs use `<metr|alrt|rel>_<normalized-name>_<8 lowercase hex random>`
and are shown as compact, accessible `(id: ...)` text beside Name, not in a separate
read-only input. IDs remain stable after generation, and draft or persisted legacy IDs
remain unchanged. This presentation and generation change preserves the backend
identifier grammar, aggregate ownership, and existing API boundaries.

v1.6 retains the existing read-only, environment-managed Data Sources lifecycle and
adds compact-default per-source disclosure of the API-supplied safe Prometheus
configuration. A trusted operator may expand an individual source locally to inspect
two-space-indented JSON containing its ID, name, credential type, a Basic-auth username
when applicable, and the exact base URL only when the API supplies it. A missing base
URL is rendered as omitted, without a replacement, validity or health inference, or
diagnostic. Bearer tokens and Basic-auth passwords remain absent from the browser-visible
contract; expanding a disclosure does not fetch, test, or mutate a source.

v1.7 retains the complete v1.6 direction and adds an advisory `Validate query` action
to Metric Lens Configuration. It reuses the existing Metric preflight API with a fixed
`15m` validation window, displays actionable single/zero/multiple-series and safe
provider feedback, never rewrites PromQL, and never gates `Apply changes` or persists
preflight state in the Observation draft. Full backend agent traces and operational
logs remain unavailable to the browser.

v1.8 retains the complete v1.7 direction and refines only Run Detail presentation. It
uses frozen Metric result identity (`metric_ref` and unit), explicit numerical,
semantic, optional-analysis, reference-period, and persisted-history groups with
bounded display formatting; it does not join mutable Observation definitions. Evidence
and Relationship references are compact accessible disclosures resolved only from the
loaded immutable run-detail response, while Knowledge references remain separate.
Persisted report Markdown is shown through a project-owned dependency-free safe subset
renderer with text-only content and exact `Copy Markdown`; HTML, links, and unsupported
Markdown stay inert. Empty copy describes what the completed result contains or does
not contain, without changing lifecycle or analytical semantics. This does not add
charts, export, provider fetches, a general Markdown engine, new APIs, or new
analytical meaning.

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

MagicPath can guide look and feel, but an approved change does not require 1:1 canvas parity or synchronization. Historical v1.1 through v1.7 wording remains historical; ADR-167 and this current v1.8 documentation govern new work.

## Usage

Before planning, implementing, or reviewing a frontend change, read:

1. `frontend_ui_stack_adr.md`
2. `ui_implementation_handoff_v1.md`
3. relevant architecture/contracts under `docs/architecture/`

For Observation Management, preserve the draft/aggregate workflow: nested Metric Lens, Alert Lens, and Relationship editors apply changes to the Observation draft; only the final `Create Observation` action submits the validated aggregate.
