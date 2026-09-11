## MODIFIED Requirements

### Requirement: Provide the Overview as the monitoring entry point

The application SHALL provide an active `Overview` navigation item at `/overview` and SHALL redirect the application root `/` to that route. The page SHALL use the accepted application shell and SHALL contain a page header, summary cards, an Observation list, Recent Findings, and Run Activity.

The Overview SHALL derive its monitoring snapshot from the existing complete Observation-definition list and the resilient newest-first Overview runtime feed. It SHALL perform read-only monitoring and SHALL NOT start, retry, cancel, repair, mutate, or delete an Observation or run. The strict Runs history and detail screens SHALL continue using their existing strict APIs.

#### Scenario: Open the application root

- **WHEN** a user opens `/`
- **THEN** the application redirects to `/overview`
- **AND** the Overview navigation item is active

#### Scenario: Load a complete monitoring snapshot

- **GIVEN** Observation definitions and only available runtime items are returned
- **WHEN** the Overview loads
- **THEN** it presents the summary, Observation list, recent findings, and run activity from durable API data
- **AND** loading the page causes no execution, repair, or configuration mutation

#### Scenario: Load a limited monitoring snapshot

- **GIVEN** the runtime feed contains available and limited items
- **WHEN** the Overview loads
- **THEN** it presents all usable monitoring information and an explicit coverage limitation
- **AND** invalid fields remain unavailable rather than suppressing the complete snapshot

#### Scenario: Load a monitoring snapshot

- **GIVEN** Observation definitions and run history are available
- **WHEN** the Overview loads
- **THEN** it presents the summary, Observation list, recent findings, and run activity from durable API data
- **AND** loading the page causes no execution or configuration mutation

### Requirement: Summarize current state without conflating analytical and execution semantics

The summary area SHALL show independently derived counts for total configured Observations, active Observations whose latest runtime item has validated `pending|running` execution status, Observations whose latest available run has each explicit analytical state, and Observations whose latest runtime item has validated `failed` execution status.

The latest runtime item for an Observation SHALL be the first matching available or limited item in the feed's newest-first order. The UI SHALL NOT fall back to an older available run when the latest item is limited. A latest limited item MAY contribute to an execution count only when its execution status was independently validated; it SHALL contribute to no analytical-state count. A failed latest item with an available persisted analytical state SHALL contribute to both corresponding counts. Never-run and missing analytical state SHALL not be classified as no significant findings.

The summary region SHALL also expose the number of configured Observations whose latest runtime item is limited, without treating that count as an analytical or execution state.

#### Scenario: Count independently valid limited execution state

- **GIVEN** an Observation's latest item is limited but preserves validated execution status `failed`
- **WHEN** summary counts are derived
- **THEN** it contributes to failed executions and limited runtime coverage
- **AND** it contributes to no analytical-state count

#### Scenario: Do not use older state as current state

- **GIVEN** the newest item for an Observation is limited and an older item is available
- **WHEN** current summary counts are derived
- **THEN** the older analytical state is not used as the Observation's current state

#### Scenario: Count independent states

- **GIVEN** an Observation's latest run is `failed` and retains analytical state `significant_findings_present`
- **WHEN** summary counts are derived
- **THEN** the Observation contributes once to the significant-findings count and once to the failed-execution count
- **AND** neither state is used to infer the other

#### Scenario: Do not classify unavailable analysis

- **GIVEN** an active, failed, cancelled, limited, or never-run Observation has no analytical state
- **WHEN** the summary renders
- **THEN** it does not count that Observation as having significant findings or no significant findings

### Requirement: Show every Observation with its latest monitoring context

The Observation list SHALL contain every configured Observation exactly once. Each row SHALL show its name, description when present, and the independently available fields from its newest runtime item: latest run time, execution status, analytical state, duration, and up to seven newest available-or-limited run markers. Every unavailable field SHALL have a field-local unavailable label; one limited field or record SHALL NOT collapse the remaining desktop columns into one spanning message.

For an Observation with no run, the row SHALL explicitly say `Not run yet`. For a limited latest item, the row SHALL show `Runtime data limited` and preserve every safe field admitted by that item. When a latest run is active, duration SHALL be presented as in progress. Rows SHALL remain ordered by latest durable item creation time newest first, followed by never-run Observations in definition order.

Observation identity SHALL navigate to Observation detail. An available latest run SHALL link to exact run detail. A limited latest item MAY link to strict run detail only when its stable run identity is available, with no promise that strict detail projection will succeed.

#### Scenario: Render a partially available row

- **GIVEN** a limited latest item has valid creation time and failed execution status but no valid analytical state or analysis window
- **WHEN** its Observation row renders
- **THEN** creation time and failed status are shown in their aligned columns
- **AND** analytical state and unavailable fields use local placeholders

#### Scenario: Preserve seven mixed markers

- **GIVEN** an Observation has available and limited recent items
- **WHEN** its row renders
- **THEN** the seven newest items retain durable order and distinct availability cues
- **AND** no marker invents an analytical or execution value

#### Scenario: Scan a mixed Observation list

- **GIVEN** configured Observations include completed, active, failed, cancelled, limited, and never-run cases
- **WHEN** the list renders
- **THEN** every Observation appears exactly once with independent execution, analytical, and availability values
- **AND** never-run Observations appear after run-backed Observations with an explicit `Not run yet` state

#### Scenario: Show recent run states accessibly

- **GIVEN** an Observation has more than seven historical runs
- **WHEN** its row renders
- **THEN** only its seven newest items are represented in newest-to-oldest order
- **AND** every marker has a textual accessible description of its durable states and availability

#### Scenario: Open the latest run

- **GIVEN** an Observation has a stable latest run identity
- **WHEN** the user activates its latest-run action
- **THEN** the application navigates to the strict detail route for that identity

### Requirement: Surface bounded recent Observation findings

Recent Findings SHALL be derived only from persisted Observation-level findings belonging to available analyzed runs, never from limited items, Lens-local findings, hypotheses, reports, execution failures, or client inference. The page SHALL inspect the five newest available run summaries that have an analytical state, load their strict run details, preserve run newest-first and finding order, and show at most five findings.

Each finding SHALL show its statement, Observation name, run time, and analytical state and link to source run detail. If limited runtime items were skipped while choosing candidates, the section SHALL disclose incomplete runtime coverage while preserving successfully loaded findings. If no inspected available run contains findings, the bounded empty message SHALL not claim that no historical or unavailable finding exists.

#### Scenario: Preserve findings beside limited data

- **GIVEN** available candidate details contain findings and other runtime items are limited
- **WHEN** Recent Findings renders
- **THEN** available persisted findings remain visible with a coverage limitation
- **AND** limited items are not converted into findings

#### Scenario: Report bounded absence honestly

- **GIVEN** inspected available runs contain no findings and limited items exist outside the inspected set
- **WHEN** the section renders
- **THEN** it reports no findings in the inspected available runs
- **AND** does not claim complete historical absence

#### Scenario: Show recent persisted findings

- **GIVEN** the five newest available analyzed runs contain more than five Observation-level findings
- **WHEN** Recent Findings renders
- **THEN** it shows the first five findings in run newest-first and persisted finding order
- **AND** each item links to the run that owns the finding

#### Scenario: Keep hypotheses and failures out of findings

- **GIVEN** inspected run details contain hypotheses, Lens-local findings, and failed executions
- **WHEN** Recent Findings is derived
- **THEN** none of those values is promoted into an Observation-level finding

#### Scenario: Report a bounded empty result honestly

- **GIVEN** none of the five newest available analyzed runs contains an Observation-level finding
- **WHEN** the section renders
- **THEN** it states that those inspected runs contain no findings
- **AND** it does not claim that the entire or limited run history has no findings

### Requirement: Present recent run activity as execution history

Run Activity SHALL represent up to the fourteen newest available-or-limited runtime items in chronological display order. Every independently validated execution status SHALL remain exactly `pending`, `running`, `completed`, `failed`, or `cancelled`. A limited item without a valid execution status SHALL appear as `Unavailable`, outside those execution-state counts. The section SHALL expose visible and accessible counts for exact represented statuses plus represented limited items and SHALL NOT map execution failure or limited data to analytical significance.

The section SHALL link to complete strict Runs history and disclose that strict history may be unavailable when limited records exist. If no runtime items exist, it SHALL present an explicit no-history state rather than implying healthy monitoring.

#### Scenario: Show mixed activity availability

- **GIVEN** the fourteen newest items include available items, limited items with valid status, and a limited item without valid status
- **WHEN** Run Activity renders
- **THEN** valid statuses contribute to their exact counts and the unknown-status item contributes only to unavailable coverage
- **AND** all represented items retain chronological position

#### Scenario: Keep strict Runs navigation honest

- **GIVEN** limited runtime items exist
- **WHEN** the user sees the Runs-history link
- **THEN** the Overview identifies that its resilient projection may contain more usable information than strict history

#### Scenario: Show mixed execution activity

- **GIVEN** the newest runtime feed contains mixed active, terminal, and limited items
- **WHEN** Run Activity renders
- **THEN** up to fourteen items are represented in chronological order with exact available execution-status semantics
- **AND** equivalent status and availability counts are available without relying on the chart alone

#### Scenario: Show no activity data

- **GIVEN** the Overview runtime feed is successfully loaded and empty
- **WHEN** Run Activity renders
- **THEN** it explains that no Observation runs exist yet
- **AND** it does not imply successful or healthy monitoring
