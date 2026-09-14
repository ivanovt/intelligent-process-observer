# overview-monitoring-refinement Specification

## Purpose

Refine the approved Overview into a dense, responsive monitoring workspace that keeps Observation state, recent findings, and execution activity simultaneously scannable without changing their domain semantics.

## Requirements

### Requirement: Present a compact monitoring header and state summary

The Overview SHALL retain its `Overview` identity, concise current-state description, manual Refresh action, and honest client-receipt refresh time.

The summary SHALL present compact counts for total configured Observations, active Observations, latest `no_significant_findings`, latest `uncertain`, latest `significant_findings_present`, and latest failed execution. Limited latest-runtime coverage SHALL be shown as a separate compact limitation count or notice rather than as an analytical or execution state.

Summary cards SHALL use neutral surface backgrounds. Semantic color SHALL accent the relevant number, icon, or small indicator: no findings uses the analytical no-findings token, uncertain uses the analytical uncertain token, significant findings uses the analytical significant token, active uses an execution-active token, and failed uses the execution-failed token. Zero, unavailable, and limited values SHALL remain legible and SHALL not fill entire cards with reassuring or alarming color. Each card SHALL include an existing Lucide icon or status indicator with an accessible text label; icon and color SHALL not carry meaning alone.

#### Scenario: Scan complete colored summary

- **WHEN** complete monitoring data renders
- **THEN** six compact neutral cards use distinct semantic value/icon accents
- **AND** analytical and execution colors retain separate token ownership

#### Scenario: Scan incomplete summary

- **GIVEN** limited latest-runtime items exist
- **WHEN** summary renders
- **THEN** usable counts remain visible and limited coverage is stated separately
- **AND** unavailable values do not appear as successful or failed classifications

#### Scenario: Scan a complete compact summary

- **GIVEN** definitions and newest-first runtime data loaded successfully
- **WHEN** the Overview summary renders
- **THEN** all six counts appear in a compact scan-oriented row or responsive grid
- **AND** analytical, active, failed, and limited meanings remain distinct

#### Scenario: Keep analytical absence out of state counts

- **GIVEN** an Observation has no run or its latest item has no analytical state
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

At desktop widths, the Observation collection SHALL use one shared non-overflowing grid definition for header and rows with columns for Observation identity, latest run time, analytical state, execution status/duration, recent runs, and a compact unlabeled action affordance. The grid SHALL fit inside the primary panel at the supported desktop breakpoint; fixed minimums SHALL not push headers or actions into the insights rail. Equivalent header and row fields SHALL align.

Each row SHALL use a safe composition-derived Lucide icon: Metric-only, Alert-only, mixed Metric/Alert, or a neutral unavailable/legacy composition. These icons SHALL describe configured composition only and SHALL NOT imply health, severity, process category, or analytical state.

Runtime-unavailable and limited rows SHALL retain the column structure and render field-local placeholders instead of one message spanning all runtime columns. Available analytical and execution states SHALL use compact project-owned dot/icon-plus-text treatments aligned with the reference hierarchy while preserving exact accepted labels. At narrow widths, rows SHALL stack with visible field labels and no horizontal page scrolling.

Each recent-run marker SHALL retain a unique visible status/availability cue, keyboard detail, and accessible exact-state label. Completed, cancelled, and limited markers SHALL remain distinguishable without color.

#### Scenario: Align headers and data

- **GIVEN** the primary desktop panel and insights rail render side by side
- **WHEN** Observation rows contain available, limited, and unavailable values
- **THEN** every field remains under its matching header within the primary panel
- **AND** the action affordance does not overlap the rail

#### Scenario: Derive composition icon safely

- **GIVEN** Metric-only, Alert-only, mixed, and legacy/empty definitions
- **WHEN** their rows render
- **THEN** each uses the corresponding composition icon and accessible label
- **AND** no icon claims a health or process-category meaning

#### Scenario: Scan aligned desktop rows

- **GIVEN** multiple loaded Observations have mixed latest states and availability
- **WHEN** the desktop collection renders
- **THEN** equivalent fields align under stable scan columns
- **AND** analytical state, execution status, and availability remain visually separate

#### Scenario: Distinguish recent execution markers

- **GIVEN** recent runs include completed, cancelled, and limited items
- **WHEN** their markers render
- **THEN** they are distinguishable without relying only on color
- **AND** their full durable descriptions are available to keyboard and assistive-technology users

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

The refined Overview SHALL follow the accepted IPO shell, typography, semantic tokens, domain components, and responsive behavior. The supplied dashboard screenshot SHALL guide density, white-surface cards, restrained borders/shadows, icon placement, dot/icon-plus-text states, and column proportions, but SHALL NOT override product semantics.

The refinement SHALL NOT add user identity, global time-range control, arbitrary category icons, health classification, ObservationRun `partial`, runtime mutation, credential exposure, data repair, or fabricated findings. Invalid durable runtime data SHALL appear through the explicit resilient Overview limitation contract; it SHALL not be silently dropped, rewritten, or used to weaken the strict Runs API.

#### Scenario: Follow visual hierarchy without copying unsupported semantics

- **WHEN** the Overview is compared with the reference
- **THEN** its surfaces, accents, icons, state treatments, density, and column alignment follow the reference hierarchy
- **AND** unsupported avatar, global range, `partial` run, and fabricated status entries remain absent

#### Scenario: Show useful content during inconsistent data

- **GIVEN** some runtime items are limited and others are valid
- **WHEN** the Overview renders
- **THEN** valid definitions, states, findings, and activity remain visible with explicit limitations
- **AND** no invalid value is inferred or hidden as healthy data

#### Scenario: Render partial runtime failure after refinement

- **GIVEN** definitions load successfully and the Overview runtime request fails before any successful snapshot
- **WHEN** the refined Overview renders
- **THEN** definitions remain searchable in the dense collection and runtime-dependent values remain unavailable
- **AND** the page does not display invented analytical or execution results

#### Scenario: Exclude unsupported reference controls

- **WHEN** the refined Overview is compared with the informative screenshot
- **THEN** no avatar, global time-range selector, ObservationRun `partial`, or fabricated normal-finding entry is required
- **AND** their omission is not considered a visual acceptance failure
