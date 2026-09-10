## Purpose

Provide a single monitoring surface where a trusted operator can quickly understand the latest durable state of every Observation, locate significant findings, and distinguish analytical concerns from execution failures.

## ADDED Requirements

### Requirement: Provide the Overview as the monitoring entry point

The application SHALL provide an active `Overview` navigation item at `/overview` and SHALL redirect the application root `/` to that route. The page SHALL use the accepted application shell and SHALL contain a page header, summary cards, an Observation list, Recent Findings, and Run Activity.

The Overview SHALL derive its monitoring snapshot from the existing complete Observation-definition list and newest-first Observation-run history. It SHALL perform read-only monitoring and SHALL NOT start, retry, cancel, mutate, or delete an Observation or run.

#### Scenario: Open the application root

- **WHEN** a user opens `/`
- **THEN** the application redirects to `/overview`
- **AND** the Overview navigation item is active

#### Scenario: Load a monitoring snapshot

- **GIVEN** Observation definitions and run history are available
- **WHEN** the Overview loads
- **THEN** it presents the summary, Observation list, recent findings, and run activity from durable API data
- **AND** loading the page causes no execution or configuration mutation

### Requirement: Summarize current state without conflating analytical and execution semantics

The summary area SHALL show four independently derived counts:

- total configured Observations;
- active Observations that currently have a `pending` or `running` run;
- Observations whose latest run has analytical state `significant_findings_present`;
- Observations whose latest run has execution status `failed`.

The latest run for an Observation SHALL be the first matching item in the API's newest-first run history. Each Observation SHALL contribute at most once to each count. A failed latest run with an already persisted significant analytical state SHALL contribute to both corresponding counts. `cancelled`, `uncertain`, missing analysis, and never-run state SHALL NOT be counted as either significant findings or failed execution.

#### Scenario: Count independent states

- **GIVEN** an Observation's latest run is `failed` and retains analytical state `significant_findings_present`
- **WHEN** summary counts are derived
- **THEN** the Observation contributes once to the significant-findings count and once to the failed-execution count
- **AND** neither state is used to infer the other

#### Scenario: Do not classify unavailable analysis

- **GIVEN** an active, failed, cancelled, or never-run Observation has no analytical state
- **WHEN** the summary renders
- **THEN** it does not count that Observation as having significant findings or no significant findings

### Requirement: Show every Observation with its latest monitoring context

The Observation list SHALL contain every configured Observation exactly once. Each row SHALL show its name, description when present, latest run time, latest execution status, latest analytical state, duration when available, and up to seven most recent runs for that Observation. The recent-run history SHALL preserve newest-to-oldest meaning and each marker SHALL expose its run time, execution status, and analytical state or analysis-unavailable state as text accessible to assistive technology rather than by color alone.

For an Observation with no run, the row SHALL explicitly say `Not run yet`; it SHALL NOT synthesize an execution status, analytical state, duration, or normal/healthy interpretation. When a latest run is still active, duration SHALL be presented as in progress rather than as zero. Rows SHALL be ordered by latest run creation time newest first, followed by never-run Observations in the definition API's order.

The Observation identity SHALL navigate to its existing Observation detail route. A row with a latest run SHALL also provide a distinct action to open that exact run at `/runs/{observationRunId}`.

#### Scenario: Scan a mixed Observation list

- **GIVEN** configured Observations include completed, active, failed, cancelled, and never-run cases
- **WHEN** the list renders
- **THEN** every Observation appears exactly once with independent execution and analytical values
- **AND** never-run Observations appear after run-backed Observations with an explicit `Not run yet` state

#### Scenario: Show recent run states accessibly

- **GIVEN** an Observation has more than seven historical runs
- **WHEN** its row renders
- **THEN** only its seven newest runs are represented in newest-to-oldest order
- **AND** every marker has a textual accessible description of its durable states

#### Scenario: Open the latest run

- **GIVEN** an Observation has a latest run
- **WHEN** the user activates its latest-run action
- **THEN** the application navigates to the detail route for that stable run identity

### Requirement: Surface bounded recent Observation findings

Recent Findings SHALL be derived only from persisted Observation-level findings, never from Lens-local findings, hypotheses, reports, execution failures, or client inference. The page SHALL inspect the five newest run summaries that have an analytical state, load their run details, preserve run newest-first order and finding order within each run, and show at most five findings.

Each finding SHALL show its statement, Observation name, run time, and analytical state, and SHALL provide an action that opens the source run detail. The section SHALL NOT add severity, confidence, probability, root-cause, recommendation, ranking, or urgency semantics. If none of the inspected runs contains findings, the section SHALL say that no findings are present in the five latest analyzed runs rather than claiming that no historical finding exists.

#### Scenario: Show recent persisted findings

- **GIVEN** the five newest analyzed runs contain more than five Observation-level findings
- **WHEN** Recent Findings renders
- **THEN** it shows the first five findings in run newest-first and persisted finding order
- **AND** each item links to the run that owns the finding

#### Scenario: Keep hypotheses and failures out of findings

- **GIVEN** inspected run details contain hypotheses, Lens-local findings, and failed executions
- **WHEN** Recent Findings is derived
- **THEN** none of those values is promoted into an Observation-level finding

#### Scenario: Report a bounded empty result honestly

- **GIVEN** none of the five newest analyzed runs contains an Observation-level finding
- **WHEN** the section renders
- **THEN** it states that those inspected runs contain no findings
- **AND** it does not claim that the entire run history has no findings

### Requirement: Present recent run activity as execution history

Run Activity SHALL represent up to the fourteen newest Observation runs in chronological display order while preserving each run's exact execution status. It SHALL distinguish `pending`, `running`, `completed`, `failed`, and `cancelled`, include a text legend or equivalent labels, and provide an accessible non-visual summary of the represented status counts. It SHALL NOT encode analytical state as execution activity or map failed execution to a significant finding.

The section SHALL link to the complete Runs history. If no runs exist, it SHALL present an explicit no-run-history state rather than an empty chart suggesting inactivity or normal operation.

#### Scenario: Show mixed execution activity

- **GIVEN** the newest run history contains mixed active and terminal execution statuses
- **WHEN** Run Activity renders
- **THEN** up to fourteen runs are represented in chronological display order with exact execution-status semantics
- **AND** equivalent status-count information is available without relying on the visual chart alone

#### Scenario: Show no activity data

- **GIVEN** run history is successfully loaded and empty
- **WHEN** Run Activity renders
- **THEN** it explains that no Observation runs exist yet
- **AND** it does not imply successful or healthy monitoring

### Requirement: Keep active monitoring current and preserve the last successful view

The Overview SHALL load Observation definitions and run history independently, provide a manual `Refresh` action, and distinguish initial loading, complete success, successful empty data, partial request failure, and complete request failure. When either source succeeds, the page SHALL preserve and present the truthful sections derivable from that source while explicitly marking dependent sections unavailable; it SHALL NOT replace a request failure with an empty collection.

While the loaded run history contains at least one `pending` or `running` run, the page SHALL periodically refresh run history and newly eligible finding detail, then stop continuous polling after active runs become terminal and perform one final refresh. Refresh SHALL preserve the displayed page and SHALL not announce the entire dashboard repeatedly to assistive technology.

After any successful snapshot is visible, a later refresh failure SHALL retain the last successful data for the affected source, mark it stale, and offer retry. A successful refresh SHALL replace data by stable identities and SHALL NOT regress a terminal run to an older active representation.

#### Scenario: Monitor an active run

- **GIVEN** loaded history contains a running Observation
- **WHEN** durable execution progresses
- **THEN** automatic refresh updates the affected summary, row, finding eligibility, and activity representation
- **AND** polling stops after terminal state with one final refresh

#### Scenario: Preserve stale monitoring data

- **GIVEN** a complete Overview snapshot is visible
- **WHEN** a later refresh of run history fails
- **THEN** the last successful run-derived values remain visible with stale feedback and retry
- **AND** the failure is not rendered as zero active runs, zero failures, or an empty history

#### Scenario: Definitions load while run history fails

- **WHEN** Observation definitions load successfully but run history fails before any successful run snapshot
- **THEN** configured Observations remain visible with runtime state explicitly unavailable
- **AND** run-derived summary counts, findings, and activity are marked unavailable rather than zero or empty

### Requirement: Preserve trusted-MVP safety and accepted visual semantics

The Overview SHALL use project-owned semantic state components and tokens, pair color with text, remain keyboard navigable, and preserve readable layout at supported narrow and desktop widths. Provider credentials, selectors, raw provider payloads, prompts, model settings, operational diagnostics, and undeclared runtime internals SHALL NOT appear.

The Overview SHALL remain inside the accepted unauthenticated trusted single-user/internal deployment boundary. It SHALL NOT add login, authorization, cross-origin access, browser-stored credentials, or a second monitoring domain model.

#### Scenario: Review states without color

- **WHEN** a user scans the Overview without perceiving semantic colors
- **THEN** execution status, analytical state, unavailable state, and recent-run markers remain distinguishable through text and accessible names

#### Scenario: Keep sensitive and internal data absent

- **WHEN** the Overview renders definitions and run data
- **THEN** it exposes only fields already admitted by the existing public Observation and run contracts
- **AND** no provider secret or orchestration-internal value is shown
