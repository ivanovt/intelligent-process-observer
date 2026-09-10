## Purpose

Refine the approved Overview into a dense, responsive monitoring workspace that keeps Observation state, recent findings, and execution activity simultaneously scannable without changing their domain semantics.

## ADDED Requirements

### Requirement: Present a compact monitoring header and state summary

The Overview SHALL retain its `Overview` identity while using a concise current-state description, the existing manual Refresh action, and a visible last-successful-refresh time after at least one monitoring source has loaded successfully. The refresh time SHALL describe client receipt of the latest successful definition or run-history response; it SHALL NOT imply a backend event time, data-source collection time, or globally consistent snapshot.

The summary SHALL present six compact counts:

- total configured Observations;
- active Observations whose latest run is `pending` or `running`;
- Observations whose latest analytical state is `no_significant_findings`;
- Observations whose latest analytical state is `uncertain`;
- Observations whose latest analytical state is `significant_findings_present`;
- Observations whose latest execution status is `failed`.

Each analytical count SHALL derive only from the latest run's explicit analytical state. Never-run Observations and runs without analysis SHALL be excluded from all three analytical counts rather than classified as normal. Execution failure SHALL remain independent, so one latest run MAY contribute to both a failed-execution count and one analytical-state count. Each count SHALL be independently unavailable when its required source data has never loaded successfully.

#### Scenario: Scan a complete compact summary

- **GIVEN** definitions and newest-first run history loaded successfully
- **WHEN** the Overview summary renders
- **THEN** all six counts appear in a compact scan-oriented row or responsive grid
- **AND** no-finding, uncertain, significant-finding, active, and failed values retain distinct labels and semantic treatment

#### Scenario: Keep analytical absence out of state counts

- **GIVEN** an Observation has no run or its latest run has no analytical state
- **WHEN** summary counts are derived
- **THEN** it contributes to none of the three analytical-state counts
- **AND** its absence is not interpreted as `no_significant_findings`

#### Scenario: Describe refresh time honestly

- **WHEN** either monitoring source completes a successful request
- **THEN** the header exposes the latest client refresh time
- **AND** the label does not claim that every backend artifact was produced at that time

### Requirement: Use a wide monitoring workspace with a persistent insights rail

At wide desktop widths, the Overview SHALL use the available application workspace as a two-column composition: the Observation collection SHALL occupy the primary wider column, and Recent Findings plus Run Activity SHALL occupy a narrower insights rail in the same initial content region. Recent Findings SHALL appear above Run Activity. A long Observation collection SHALL NOT force both insight sections to begin only after the final Observation row.

At narrower widths, the composition SHALL become one column in this order: summary, Observations, Recent Findings, Run Activity. Content SHALL not require horizontal page scrolling. Existing unavailable, loading, stale, and empty feedback SHALL remain adjacent to the affected content and SHALL not become a visually dominant replacement for successful data.

#### Scenario: Scan on a wide desktop

- **WHEN** the available content width supports the desktop composition
- **THEN** Observations and the insights rail are visible beside one another
- **AND** Recent Findings and Run Activity are not positioned beneath the entire Observation collection

#### Scenario: Use the Overview at a narrow width

- **WHEN** the available content width cannot preserve readable table columns and insights rail
- **THEN** the sections stack in the specified order without horizontal page scrolling
- **AND** every state, action, and navigation target remains available

### Requirement: Provide local Observation search

The Observation section SHALL provide a search field that filters only the successfully loaded Observation rows already available in the browser. Search SHALL use a trimmed, case-insensitive substring match against Observation name and description. An absent description SHALL behave as an empty value. Search SHALL preserve the approved latest-run ordering among matched rows and SHALL NOT issue a backend query, mutate data, change summary counts, or filter Recent Findings or Run Activity.

An empty query SHALL show all loaded Observation rows. A non-empty query with no matches SHALL show a distinct no-match state with a clear-search action; it SHALL NOT be presented as an empty configured collection or runtime failure. The search field SHALL have a visible label or accessible name and keyboard-operable clearing behavior.

#### Scenario: Filter loaded Observations

- **GIVEN** loaded rows contain names and descriptions with mixed letter case
- **WHEN** the user enters a query with surrounding whitespace
- **THEN** rows whose name or description contains the trimmed query case-insensitively remain in their original order
- **AND** no new API request is made

#### Scenario: Clear a no-match result

- **GIVEN** a non-empty search matches no loaded Observation
- **WHEN** the no-match state appears
- **THEN** it is distinct from an empty definition list
- **AND** the user can clear the query and restore all loaded rows

### Requirement: Render Observations as a dense semantic table/list

At desktop widths, the Observation collection SHALL use a compact aligned header and row structure with these scan columns:

- Observation identity and optional description;
- latest run time;
- latest analytical state;
- latest execution status and duration;
- up to seven newest run states;
- an action to open the latest run when available.

The collection SHALL use lightweight dividers and row hover/focus treatment rather than a separate large bordered card for every Observation. It SHALL remain a project-owned lightweight component and SHALL NOT require advanced table behavior or introduce TanStack Table solely for this presentation.

At narrow widths, each row SHALL reflow into a compact stacked item while retaining the same information and navigation. Observation identity SHALL continue to open Observation detail. Never-run and runtime-unavailable rows SHALL retain their explicit accepted labels and SHALL not receive invented status values.

Each recent-run marker SHALL have a unique visible status cue, keyboard-available explanatory text or tooltip, and an accessible label containing run time, exact execution status, and analytical state or analysis-unavailable state. `completed` and `cancelled` SHALL not use the same visible text token without another non-color distinction.

#### Scenario: Scan aligned desktop rows

- **GIVEN** multiple loaded Observations have mixed latest states
- **WHEN** the desktop collection renders
- **THEN** equivalent fields align under stable scan columns
- **AND** analytical state and execution status remain visually separate

#### Scenario: Distinguish recent execution markers

- **GIVEN** recent runs include both `completed` and `cancelled`
- **WHEN** their markers render
- **THEN** they are distinguishable without relying only on color
- **AND** their full durable state descriptions are available to keyboard and assistive-technology users

### Requirement: Keep true findings and exact execution activity visible

The insights rail SHALL preserve the approved Recent Findings source, five-analyzed-run inspection bound, five-finding display bound, ordering, incomplete-state behavior, and source-run navigation. It SHALL display only persisted Observation-level findings. It SHALL NOT add entries that merely say an Observation has no findings, promote hypotheses or Lens-local findings, or attach severity, urgency, confidence, or finding-count semantics not present in the public contract.

Run Activity SHALL retain its fourteen-newest-run bound and exact `pending`, `running`, `completed`, `failed`, and `cancelled` statuses. In addition to the accessible non-visual summary, it SHALL show a compact visible count for every exact status represented by the chart and the total number of represented runs. It SHALL NOT introduce `partial` as an ObservationRun status. The chart and counts SHALL describe only the bounded represented runs, not all historical runs.

#### Scenario: Keep the insights rail semantically honest

- **GIVEN** inspected runs include findings, hypotheses, no-finding analyses, and failed executions
- **WHEN** Recent Findings renders
- **THEN** only persisted Observation-level findings become finding entries
- **AND** other analytical or execution outcomes are not rewritten as findings

#### Scenario: Show bounded activity totals

- **GIVEN** fourteen represented runs contain all accepted execution statuses
- **WHEN** Run Activity renders
- **THEN** the visible status counts and total describe exactly those fourteen runs
- **AND** no ObservationRun `partial` count or state is shown

### Requirement: Treat the visual reference as informative and preserve failure honesty

The refined Overview SHALL follow the accepted ObserveAI shell, typography, semantic tokens, domain components, and responsive behavior. The supplied dashboard screenshot MAY inform density, spacing, hierarchy, and column proportions but SHALL NOT be a parity requirement or authority for product semantics.

The refinement SHALL NOT add a user avatar or identity, authentication behavior, global time-range control, arbitrary Observation category icons, new health classification, runtime mutation, backend endpoint, credential exposure, or data repair. If run history remains unavailable because the public API rejects invalid durable data, the page SHALL continue to show the accepted unavailable/stale state while keeping successfully loaded definitions searchable and visible; it SHALL NOT fabricate dashboard counts or suppress the failure to resemble the reference.

#### Scenario: Render partial runtime failure after refinement

- **GIVEN** definitions load successfully and run history fails before any successful runtime snapshot
- **WHEN** the refined Overview renders
- **THEN** definitions remain searchable in the dense collection and runtime-dependent values remain unavailable
- **AND** the page does not display invented analytical or execution results

#### Scenario: Exclude unsupported reference controls

- **WHEN** the refined Overview is compared with the informative screenshot
- **THEN** no avatar, global time-range selector, ObservationRun `partial`, or fabricated normal-finding entry is required
- **AND** their omission is not considered a visual acceptance failure
