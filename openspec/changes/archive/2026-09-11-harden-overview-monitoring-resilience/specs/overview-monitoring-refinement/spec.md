## MODIFIED Requirements

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

### Requirement: Treat the visual reference as informative and preserve failure honesty

The refined Overview SHALL follow the accepted ObserveAI shell, typography, semantic tokens, domain components, and responsive behavior. The supplied dashboard screenshot SHALL guide density, white-surface cards, restrained borders/shadows, icon placement, dot/icon-plus-text states, and column proportions, but SHALL NOT override product semantics.

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
