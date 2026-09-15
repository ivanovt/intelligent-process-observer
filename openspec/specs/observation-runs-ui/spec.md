# observation-runs-ui Specification

## Purpose

Let engineers launch Observations, monitor all active and historical runs, and inspect a broad first version of each run's durable analytical detail.

## Requirements

### Requirement: Provide a top-level Runs history screen

The application SHALL activate the existing `Runs` navigation item at `/runs` and present all Observation runs returned by the public API in newest-first order. The screen SHALL use the accepted IPO shell, semantic tokens, lightweight rows/cards, and project-owned execution and analytical state components rather than introduce a separate administrative or visual system.

Each row SHALL present a brief scan-oriented summary: Observation name, compact run identity, analysis window or run time, duration when available, execution status, optional analytical state, and an `Open` action. Execution success SHALL be represented only by `completed`; `failed` and `cancelled` SHALL remain distinct non-success terminal states. “Issues found” SHALL map only to `significant_findings_present`; missing analysis SHALL be labeled unavailable or pending and SHALL never be inferred from execution status.

#### Scenario: Scan mixed runs

- **GIVEN** the API returns active and terminal runs with mixed optional analytical states
- **WHEN** the Runs screen renders
- **THEN** rows appear newest first with concise identity, timing, execution, and analytical information
- **AND** a failed run without analysis is not presented as having significant findings or no findings

#### Scenario: Open run detail

- **WHEN** a user activates a row's `Open` action
- **THEN** the application navigates to `/runs/{observationRunId}`

### Requirement: Filter the loaded run history by primary dimensions

The Runs screen SHALL provide independently combinable local filters for Observation, execution status, and analytical state over the complete loaded history. Observation choices SHALL be derived from the returned runs without duplicates. The analytical-state filter SHALL include an explicit unavailable/not-yet-produced value so active, early-failed, and cancelled runs can be selected without inventing an analytical classification.

Filters SHALL preserve the API's newest-first order, SHALL not trigger new execution, and SHALL be organized so additional dimensions can be added without changing row semantics. A no-match state SHALL explain that filters excluded all loaded runs and offer a clear-filters action.

#### Scenario: Combine filters

- **WHEN** a user selects one Observation, execution status `failed`, and analytical state unavailable
- **THEN** only runs matching all three dimensions remain visible in their original newest-first order

#### Scenario: Clear a no-match result

- **GIVEN** active filters match no loaded run
- **WHEN** the no-match state is shown
- **THEN** it is distinct from an empty run history
- **AND** the user can clear all filters in one action

### Requirement: Represent loading, empty, failure, and refresh states honestly

The screen SHALL distinguish initial loading, retryable request failure, an empty successful history, a filtered no-match result, and a populated history. It SHALL provide a manual `Refresh` action. While at least one loaded run is `pending` or `running`, it SHALL periodically refresh the list; it SHALL stop continuous polling when no active run remains and perform a final refresh after observing terminal state.

Automatic refresh failures SHALL retain the last successful list, show non-destructive stale/error feedback, and allow manual retry. Refreshing SHALL not reset active filters or announce the entire list repeatedly to assistive technology.

#### Scenario: Refresh active history automatically

- **GIVEN** at least one loaded run is pending or running
- **WHEN** the polling interval elapses
- **THEN** the UI reloads run history without changing filters or navigation
- **AND** lifecycle and analytical state advance only from returned durable data

#### Scenario: Preserve stale data after polling failure

- **GIVEN** a successful list is visible
- **WHEN** a later automatic refresh fails
- **THEN** the prior list remains visible with stale/error feedback
- **AND** the failure is not rendered as an empty history

### Requirement: Launch a run from a Grafana-inspired time-range dialog

The Runs screen SHALL provide a `Run Observation` action that opens an accessible dialog and independently requests current Observation Definitions from `GET /api/v1/observations`; it SHALL NOT derive launch choices only from run history. The dialog SHALL distinguish definition loading, retryable definition-request failure, successful empty definitions, and successful non-empty definitions. Confirmation SHALL remain disabled until definitions load successfully and the user selects one eligible definition. Failure SHALL offer Retry without presenting an empty collection. A successful empty collection SHALL explain that no Observation is available and offer navigation to `New Observation`.

Every returned definition SHALL appear exactly once in deterministic API order, including an Observation with no prior run. Current run history SHALL only annotate/disable definitions known to have `pending|running` runs; stale or racing history remains subject to authoritative server conflict handling. Closing the dialog SHALL abort an in-flight definition request and SHALL NOT launch or mutate a run.

The dialog SHALL contain an Observation selector and three mutually exclusive time-range modes. `Relative range` SHALL include `Last 5 minutes`, `Last 15 minutes`, `Last 30 minutes`, `Last 1 hour`, `Last 3 hours`, `Last 6 hours`, `Last 12 hours`, `Last 24 hours`, `Last 2 days`, and `Last 7 days`. `Expressions` SHALL contain `From` and `To` fields and support exactly `now`, `now-15m`, and `now-1h`. `Absolute UTC` SHALL contain explicitly UTC-labeled `From` and `To` date-time fields that accept valid calendar values with second-level precision and do not interpret them in the browser's local timezone. The initial mode SHALL remain `Relative range` with `Last 15 minutes`, equivalent at confirmation to `now-15m` through `now`.

The client SHALL resolve the selected mode against one captured current instant per validation or confirmation attempt, produce aware UTC timestamps, require `from < to` and a non-future end, show the concrete UTC range for review, and submit only those concrete timestamps to `POST /api/v1/observation-runs`. It SHALL reject an absent or invalid absolute endpoint and unsupported Grafana expressions rather than partially parse, normalize, or guess them. Switching among modes SHALL NOT reinterpret an absolute wall-clock value as browser-local time.

Observation choices SHALL identify any currently active Observation and disable it with explanatory text. The server SHALL remain authoritative: a race returning `409 Conflict` SHALL update the feedback with the existing active run and SHALL NOT be treated as successful duplicate execution.

#### Scenario: Launch from a relative preset

- **WHEN** a user selects an eligible Observation and `Last 1 hour` and confirms
- **THEN** the UI resolves one UTC window ending at the captured current instant and beginning exactly one hour earlier
- **AND** submits one launch request with concrete timestamps

#### Scenario: Load a never-run Observation

- **GIVEN** an Observation Definition exists but no run-history item references it
- **WHEN** the definition request succeeds and the dialog renders choices
- **THEN** that Observation is selectable exactly once in API order
- **AND** no synthetic run-history item is required

#### Scenario: Definitions are still loading

- **WHEN** the launch dialog's definition request is pending
- **THEN** it presents a loading state and disables confirmation
- **AND** does not infer choices from run history

#### Scenario: Definition loading fails

- **WHEN** the definition request fails
- **THEN** the dialog presents retryable error feedback and disables confirmation
- **AND** does not present the failure as an empty definition collection

#### Scenario: No definitions exist

- **WHEN** the definition request succeeds with an empty array
- **THEN** the dialog presents an explicit no-Observations state with a `New Observation` action
- **AND** sends no launch request

#### Scenario: Retry definition loading

- **GIVEN** definition loading previously failed
- **WHEN** the user activates Retry and the request succeeds
- **THEN** the selector shows the returned definitions
- **AND** confirmation remains disabled until an eligible definition is selected

#### Scenario: Launch from supported expressions

- **WHEN** a user enters `now-15m` for From and `now` for To and confirms
- **THEN** both expressions resolve from the same captured current instant
- **AND** the submitted window spans exactly 15 minutes

#### Scenario: Launch an absolute UTC interval

- **WHEN** a user enters `2026-09-10 10:00:00 UTC` for From and `2026-09-10 17:00:00 UTC` for To and confirms after that interval
- **THEN** the dialog previews and submits the exact canonical UTC timestamps `2026-09-10T10:00:00.000Z` and `2026-09-10T17:00:00.000Z`
- **AND** the values are unchanged by the browser's local timezone

#### Scenario: Reject an incomplete or invalid absolute interval

- **WHEN** either absolute endpoint is absent or is not a valid UTC calendar date-time
- **THEN** the dialog presents actionable validation feedback and disables confirmation
- **AND** sends no launch request

#### Scenario: Reject a reversed absolute interval

- **WHEN** an absolute From value is equal to or later than its To value
- **THEN** the dialog explains that From must be earlier than To
- **AND** sends no launch request

#### Scenario: Reject a future absolute interval

- **WHEN** an absolute To value is later than the captured current instant
- **THEN** the dialog explains that To cannot be in the future
- **AND** sends no launch request

#### Scenario: Reject unsupported date math

- **WHEN** a user enters an expression other than `now`, `now-15m`, or `now-1h`
- **THEN** the dialog presents actionable validation feedback
- **AND** sends no launch request

#### Scenario: Block a known active Observation

- **GIVEN** the loaded history contains an active run for an Observation
- **WHEN** the launch dialog opens
- **THEN** that Observation cannot be selected for another run
- **AND** other eligible Observations remain selectable

#### Scenario: Close while definitions are loading

- **WHEN** the user closes the dialog during the definition request
- **THEN** the request is aborted and no run is launched
- **AND** reopening starts a fresh definition load

### Requirement: Return to refreshed history after launch

After a successful `202 Accepted` launch, the dialog SHALL close, the application SHALL remain on `/runs`, and the returned acceptance snapshot SHALL become visible as an active row without navigating to detail. The screen SHALL show concise launch confirmation and enter automatic refresh behavior. The snapshot MAY already be superseded by a fast terminal continuation; the next list refresh SHALL replace it by stable run identity with current durable state and SHALL NOT regress a terminal row back to running. A failed, rejected, or conflicting launch SHALL retain the chosen values for correction or retry and SHALL NOT imply that a new run exists.

#### Scenario: Return to list after accepted launch

- **WHEN** the launch API returns `202 Accepted`
- **THEN** the user remains on the Runs screen and sees the new active run
- **AND** automatic refresh monitors it toward terminal state

#### Scenario: Refresh an immediately completed launch

- **GIVEN** the acceptance snapshot is running but the continuation already became terminal
- **WHEN** the post-launch list refresh returns that stable run identity in terminal state
- **THEN** the row advances to the durable terminal representation
- **AND** no later acceptance-snapshot update can regress it to running

#### Scenario: Retain launch input after failure

- **WHEN** launch fails before a new run is accepted
- **THEN** the dialog preserves the selected Observation and time range
- **AND** presents safe retryable or validation feedback

### Requirement: Provide a broad run-detail foundation

The route `/runs/{observationRunId}` SHALL present a run header and navigable `Summary`, `Metrics`, `Alerts`, `Relationships`, `Analysis`, and `Report` sections using only data available from the run-detail API. The header SHALL show Observation identity/name, compact run identity, exact analysis window, start/finish/duration where available, execution status, optional structured failure/cancellation reason, and optional analytical state as independent values.

`Summary` SHALL show lifecycle progress, Lens outcome counts, availability/limitations, and key findings when present. `Metrics` and `Alerts` SHALL show their LensRuns separately with Lens identity, status, reason, and the available type-specific result's accepted current/reference evidence and findings without exposing provider configuration. `Relationships` SHALL keep applicability separate from evaluation state and show conditions/evidence preserved by each evaluation. `Analysis` SHALL keep limitations, findings, hypotheses, Evidence references, Relationship references, and Knowledge references visually and structurally distinct. `Report` SHALL present the persisted Markdown content as a presentation-only artifact with a Copy Markdown action and SHALL create no analytical content.

Unavailable sections SHALL explain whether execution is still progressing, failed before the artifact was produced, was cancelled, or legitimately produced an empty collection. The foundation SHALL not invent severity, confidence, probability, root cause, recommendation, or missing analytical artifacts.

#### Scenario: Inspect a completed run

- **GIVEN** a completed run contains all supported artifacts
- **WHEN** detail loads
- **THEN** each artifact is presented in its semantically correct section with traceability intact
- **AND** the report does not replace the structured analysis views

#### Scenario: Inspect a partially populated active run

- **GIVEN** an active run has some terminal LensRuns but no ObservationAnalysisResult or report
- **WHEN** detail loads
- **THEN** committed Lens progress is visible
- **AND** Analysis and Report explain that their artifacts are not yet available

#### Scenario: Inspect a failed run after reasoning

- **GIVEN** a run has failed after persisting an ObservationAnalysisResult but before persisting a report
- **WHEN** detail loads
- **THEN** the failed execution status and available analytical state/findings are both shown
- **AND** Report explains its absence without discarding the analysis

### Requirement: Keep active run detail current and accessible

While the displayed run is pending or running, the detail view SHALL periodically reload its durable detail, preserve the current section and focus context, and stop continuous polling after terminal state with one final refresh. Manual refresh, initial loading, retryable failure, missing-run, and stale-data states SHALL be explicit. Status and state indicators SHALL always include text and accessible names rather than rely on color alone.

#### Scenario: Follow an active run in detail

- **GIVEN** a user opens a running run
- **WHEN** durable stages complete over time
- **THEN** automatic refresh reveals forward lifecycle and artifact progress without changing the selected section

#### Scenario: Run detail is unavailable

- **WHEN** the detail endpoint returns `404 Not Found`
- **THEN** the UI presents a missing-run state with a path back to Runs
- **AND** does not present the run as empty, successful, or free of findings

### Requirement: Present Metric run evidence through explicit semantic fields

The run-detail Metrics section SHALL render accepted Metric result fields explicitly rather than enumerating arbitrary runtime object entries or applying generic object-to-string conversion. For a usable result, it SHALL present the Metric reference and unit as the primary Lens identity, retain a compact Lens ID as secondary traceability, and keep current numerical evidence, semantic state, optional analytical results, reference-period comparisons, and History visually distinct.

Numerical values SHALL use consistent bounded display precision without changing persisted values. Mean, standard deviation, minimum, and maximum SHALL be formatted for scanning; slope SHALL retain enough significant precision to distinguish a small non-zero value from zero. Reference-period presentation SHALL show current and reference means plus the accepted `relative_level_change` using an explicit label such as `symmetric relative change`; it SHALL NOT describe that value as ordinary percentage increase or decrease. Full exact values remain available from the unchanged run-detail payload and are not rewritten or persisted by the UI.

Optional `spike`, `oscillation`, and `stuck_signal` results SHALL display their semantic state and relevant accepted evidence when present. Explicit `absent` and `unknown` states SHALL remain distinct from a `null` or omitted result, which SHALL be labeled only as unavailable in this result because the public artifact does not preserve whether the tool was unrequested, not applicable, or otherwise produced no semantic section. None of these cases SHALL render as `[object Object]`, the literal word `null`, zero, normality, or a fabricated result.

#### Scenario: Inspect usable Metric evidence

- **GIVEN** a completed Metric result contains numerical evidence, semantic current state, and a successful spike result
- **WHEN** the Metrics section renders
- **THEN** the user sees named formatted numerical values and the spike state/evidence in separate semantic groups
- **AND** no structured object is coerced into generic text

#### Scenario: Preserve a small non-zero slope

- **GIVEN** a Metric slope is finite, non-zero, and smaller than the normal fixed-decimal display threshold
- **WHEN** it is formatted for the UI
- **THEN** the display retains a meaningful non-zero representation
- **AND** the underlying value is not rounded or persisted differently

#### Scenario: Explain symmetric reference change

- **GIVEN** current mean `2.28`, reference mean `1.04`, and `relative_level_change=0.7456`
- **WHEN** reference evidence is displayed
- **THEN** the UI identifies `0.7456` as a symmetric relative change rather than “74.56% higher”
- **AND** current and reference means are both visible for interpretation

#### Scenario: Preserve only supported optional-analysis distinctions

- **GIVEN** one optional result is explicitly `unknown`, another is explicitly `absent`, and a third is `null`
- **WHEN** the Metric result renders
- **THEN** the explicit states use distinct labels and the null result is labeled unavailable in this result
- **AND** the UI does not infer whether the null result was unrequested, not applicable, failed, or otherwise unproduced

### Requirement: Browse Metric Lens outcomes within one run

The Run Detail `Metrics` section SHALL show one selectable card for every Metric LensRun in the loaded durable run-detail response, including pending, running, completed, partial, failed, cancelled, and completed-insufficient outcomes. It SHALL show the total Metric LensRun count and whether zero or one card is selected without describing every outcome as analyzed. No card SHALL be selected and no detail pane SHALL be rendered when the section first opens, even when results are present. Selecting a card SHALL identify it visibly and programmatically and open only that card's detail. Dismissing the pane SHALL clear selection and restore the card list to the available content width. With a pane open at a usable desktop width, including an approximately 1200px browser window with the application sidebar, the card area SHALL remain wider than the pane. The pane SHALL stay at a stable viewport position while the page and card list scroll, SHALL keep its close control reachable, and SHALL allow tall detail content to scroll independently without hiding accepted evidence. The card summary SHALL reflow rather than clip at that split width. At widths too narrow for both readable columns, cards and selected detail SHALL remain usable in sequence without horizontal clipping or lost information. An empty Metric collection SHALL retain the run-detail empty-state meaning.

#### Scenario: Compare mixed outcomes

- **GIVEN** a run detail contains completed, partial, and failed Metric LensRuns
- **WHEN** the Metrics section opens
- **THEN** all three appear in response order, none is selected, no detail pane appears, and the header shows three Metric Lenses and zero selected
- **AND** the failed Lens remains selectable without being described as successfully analyzed

#### Scenario: Select and dismiss detail

- **WHEN** the user selects a Metric LensRun and then dismisses the detail
- **THEN** only the selected Lens's detail is shown before dismissal, and no detail pane is rendered afterward
- **AND** the list remains available for a new selection

#### Scenario: Keep a closed pane closed during refresh

- **GIVEN** the Metrics section is open with no card selected
- **WHEN** automatic or manual refresh succeeds
- **THEN** refreshed cards remain visible without opening a detail pane or selecting a card

#### Scenario: Use the Metrics section at a narrow width

- **WHEN** the Metrics section is viewed at a narrow viewport
- **THEN** every Lens item can be selected and its full detail can be read in a stacked layout
- **AND** no evidence is hidden solely because the side-by-side layout does not fit

#### Scenario: Keep selected detail visible while scrolling desktop cards

- **GIVEN** a run has many Metric cards and one detail pane is open at an approximately 1200px or wider desktop window
- **WHEN** the user scrolls several cards down the page
- **THEN** the selected detail stays visible at a stable viewport position while the card list remains scrollable
- **AND** its close action and all detail evidence remain reachable through the pane's own scroll
- **AND** the card's semantic band and ordered evidence summary remain readable at the narrower desktop split

### Requirement: Summarize each Metric Lens without overstating its evidence

Each Metric card SHALL present information in this scanning order: frozen measurement identity, data quality when available, and Lens execution status; available start time and duration; a visually distinct semantic-state area; then a compact evidence summary. When a Metric result supplies frozen `metric_ref` and unit, those SHALL be the primary measurement identity and the exact Lens ID SHALL remain accessible as secondary traceability. If no result is available, the Lens ID SHALL identify the card without fetching a mutable Observation Definition or inventing a Lens name. A usable good/degraded result SHALL show mandatory current trend direction, trend rate, and variability as three labelled items in the semantic-state area. Its evidence summary SHALL present mean, range (minimum–maximum), slope, returned reference-period availability, and persisted-History direction/pattern in that order. It SHALL retain bounded number formatting and SHALL show only returned reference offsets; absence SHALL NOT be attributed to a guessed configured offset. Completed-insufficient, failed, cancelled, pending, and running outcomes SHALL display an explicit unavailable semantic state and explain why current numerical evidence is unavailable instead of rendering a fabricated descriptor or zero. Partial results SHALL show usable current evidence alongside the supported limitation/reason. Cards SHALL use a leading meaning-aligned trend or failure icon and smaller trend/availability cues within the semantic/evidence groups; icons SHALL be decorative and never replace text. Status, quality, and semantic cues SHALL use text as well as color.

#### Scenario: Scan a usable partial result

- **GIVEN** a partial Metric result has good current data, increasing/moderate trend, high variability, and reason `reference_unavailable`
- **WHEN** its list item renders
- **THEN** Partial, data quality good, current trend and variability, and available numerical evidence remain distinct
- **AND** the reference limitation is visible without recasting the Lens as failed or the current evidence as unavailable

#### Scenario: Scan the card in the mock's evidence order

- **GIVEN** a usable Metric result contains current evidence, a returned `1d` reference comparison, and persisted History
- **WHEN** its card renders
- **THEN** the labelled semantic-state band shows trend direction, trend rate, and variability before the evidence summary
- **AND** the evidence summary shows mean, minimum–maximum range, slope, `1d` reference availability, and History direction/pattern in that order
- **AND** the trend and availability icons reinforce their adjacent text without adding analytical meaning

#### Scenario: Scan a failed Metric result

- **GIVEN** a failed Metric LensRun has a failed Metric artifact with frozen identity and a safe failure reason
- **WHEN** its item renders
- **THEN** it shows Failed, the available frozen identity, and the safe reason
- **AND** the semantic-state area explicitly says unavailable, with no data-quality success badge, current-state descriptor, or numerical value

#### Scenario: Inspect a Lens before its artifact exists

- **GIVEN** a running Metric LensRun has no result artifact
- **WHEN** its item renders
- **THEN** the Lens ID and Running status identify it
- **AND** no metric reference, quality, or analysis value is inferred from a current definition

### Requirement: Inspect the selected Metric result by evidence perspective

The selected-Lens detail SHALL identify the exact selected Lens and its execution status. For a usable Metric result, it SHALL keep current semantic state, current numerical evidence, optional analyses, reference-period comparisons, and persisted History in separate, named groups. It SHALL retain the existing bounded number formatting, including meaningful non-zero slope precision, and SHALL expose accepted optional-analysis evidence when present. Explicit `present`, `absent`, and `unknown` optional states SHALL stay distinct; a null or omitted optional section SHALL be described only as unavailable in this result. A completed-insufficient or failed result SHALL show its available identity and safe limitation/error without presenting absent analytical groups as normal findings. The UI SHALL NOT create Lens-level finding, severity, confidence, or root-cause claims from these fields.

#### Scenario: Inspect one usable Lens

- **GIVEN** the selected Metric result contains current evidence, a spike result, reference comparisons, and History
- **WHEN** its detail renders
- **THEN** each evidence perspective appears in its own named group with its accepted values
- **AND** current-window trend is not presented as persisted-History direction

#### Scenario: Keep optional-analysis distinctions

- **GIVEN** spike is explicitly `unknown`, oscillation is explicitly `absent`, and stuck-signal is null
- **WHEN** the selected result renders
- **THEN** the three sections state unknown, absent, and unavailable in this result respectively
- **AND** null is not interpreted as unrequested, failed, normal, or zero

### Requirement: Explain reference and History availability from the public result

The selected detail SHALL render each returned reference-period comparison with its actual offset, current and reference means, and `relative_level_change` labelled as a symmetric relative change, together with the accepted comparison/evidence fields. It SHALL NOT infer a configured but missing offset from absent entries or describe symmetric relative change as an ordinary percentage increase/decrease. It SHALL keep persisted History separate from reference periods, show its direction, pattern, number of referenced prior runs, and supported transition evidence when available, and SHALL NOT construct or chart a raw historical sequence. If reference or History sections are absent, it SHALL distinguish a supported partial limitation from a section simply unavailable in the result without claiming that an unreturned configured period succeeded or that missing history proves a stable signal.

#### Scenario: Show returned reference periods only

- **GIVEN** one usable partial result returns a `1d` comparison and has reason `reference_unavailable`
- **WHEN** the detail renders
- **THEN** it shows the `1d` comparison and identifies the reference limitation
- **AND** it does not guess the offset or values of any unavailable comparison

#### Scenario: Show symmetric relative change

- **GIVEN** a returned reference has current mean `2.28`, reference mean `1.04`, and `relative_level_change=0.7456`
- **WHEN** the detail renders
- **THEN** it labels `0.7456` as a symmetric relative change alongside both means
- **AND** it does not call the value a 74.56% increase

#### Scenario: History is unavailable

- **GIVEN** a Metric result has no History and reason `history_analysis_failed`
- **WHEN** the detail renders
- **THEN** it explains the History limitation while retaining available current evidence
- **AND** it does not infer a sustained, stable, or empty historical trend

### Requirement: Keep Metric selection and context coherent during refresh and navigation

The Metrics section SHALL use the existing run-detail refresh and active-run polling behavior. On each successful response, it SHALL present that response's coherent durable snapshot and preserve an explicitly selected Lens by stable LensRun ID while that ID remains present; if the selected ID is absent, it SHALL clear selection and close the pane rather than select another card. If no card is selected, refresh SHALL leave the pane closed. It SHALL display a last-updated label for the latest successful client refresh rather than the Metric result generation time. A failed refresh with previously loaded data SHALL keep that data and the current selection or closed state visible with explicit stale-data feedback. A selected-Lens action to the existing run-level Analysis section SHALL be labelled `View Observation analysis` and SHALL NOT imply a separate Lens-only analysis. The Metrics detail SHALL NOT show Time series, Logs, or JSON tabs, nor expose provider queries, raw samples, operational logs, or internal diagnostics.

#### Scenario: Refresh while a Lens is selected

- **GIVEN** the second Metric LensRun is selected and a newer durable response still contains its ID
- **WHEN** automatic or manual refresh succeeds
- **THEN** the second Lens remains selected and its displayed content advances to the newer snapshot
- **AND** the user remains in the Metrics section

#### Scenario: Refresh fails after successful loading

- **GIVEN** a Metric Lens is selected in a loaded run detail
- **WHEN** a later refresh fails
- **THEN** the last successful result and selection remain visible with stale-data feedback
- **AND** the last-updated label does not advance

#### Scenario: Selected Lens disappears from refreshed results

- **GIVEN** a Metric Lens is selected and its LensRun ID is absent from a newer durable response
- **WHEN** that response renders
- **THEN** the former selection is cleared and the detail pane closes
- **AND** no other card is automatically selected

#### Scenario: Open the run-level analysis

- **WHEN** the user activates `View Observation analysis` from a selected Metric Lens
- **THEN** the existing Analysis section of the same Observation run opens
- **AND** the action does not claim that the Analysis section is a Lens-local result

### Requirement: Make structured analysis traceability understandable on demand

The Analysis section SHALL keep Finding, Hypothesis, Evidence, Relationship, and Knowledge semantics distinct while making each available reference inspectable. Each finding that has Evidence or Relationship references SHALL place all of its reference controls in one accessible `References` disclosure that is collapsed when the finding first renders. Expanding that container SHALL expose the existing independently collapsed reference controls; each control's concise label SHALL show its source type, compact source identity, and locator. Expanding or focusing an individual control SHALL reveal the exact source ID, a human-readable locator path, and the referenced value or state when that value can be resolved from the already loaded run-detail response.

The UI SHALL resolve references without fetching provider data, changing analysis, interpreting knowledge as evidence, or inventing a value when the locator is absent or cannot be resolved. Multiple references to the same source but different locators SHALL remain distinguishable. Unknown source types, missing source artifacts, and invalid locator paths SHALL show traceability unavailable rather than throwing, hiding the finding, or displaying a fabricated value. Findings with no Evidence or Relationship references SHALL not render an empty `References` disclosure; Knowledge references SHALL remain separately presented with their owning hypothesis.

#### Scenario: Open a finding's references only when needed

- **GIVEN** one finding has multiple Metric-result and Relationship-evaluation references
- **WHEN** the Analysis section first renders
- **THEN** the finding statement is visible while its `References` container is collapsed
- **AND** expanding the container exposes distinct collapsed controls for every reference without fetching additional data

#### Scenario: Inspect two references to one Metric result

- **GIVEN** one finding cites `current_state.trend.direction` and `evidence.current.mean` from the same LensRun
- **WHEN** its `References` container and each reference control are expanded
- **THEN** the controls distinguish the two locator paths and show their corresponding already-loaded values

#### Scenario: Preserve unresolved traceability honestly

- **GIVEN** a reference identifies a missing source or an unresolvable locator
- **WHEN** its owning finding's `References` container and reference control are expanded
- **THEN** the finding remains visible and the reference reports that traceability is unavailable
- **AND** the UI performs no provider request and invents no replacement value

### Requirement: Present persisted Markdown as a safe formatted report with exact-copy access

The Report section SHALL present non-empty persisted Markdown as a readable document rather than as one raw preformatted block. Without adding a dependency, it SHALL support the renderer-owned subset needed for headings, paragraphs, blockquotes, unordered lists, inline code, and strong emphasis. Strong emphasis SHALL render as semantic `<strong>` text only for well-formed renderer-owned `**text**` spans; raw HTML SHALL not be interpreted, links SHALL not become active navigation, and unsupported or malformed Markdown constructs SHALL fall back to visible plain text rather than being dropped or executed. All report content SHALL be inserted as text.

The rendered report SHALL visually emphasize deterministic finding numbers and factual values marked by the report renderer, including Metric/Lens identifiers, timestamps, durations, and numeric measurements with their units, without creating, removing, reordering, summarizing, or reinterpreting analytical content. The existing `Copy Markdown` action SHALL copy the exact persisted `report.content` byte-for-byte; visible formatting SHALL not mutate the artifact. Legacy or alternate valid Markdown layouts SHALL remain readable through the safe fallback behavior.

#### Scenario: Read a generated report

- **GIVEN** persisted report content contains renderer-owned headings, blockquotes, lists, inline-code identifiers, and strong-emphasis spans for finding numbers and factual values
- **WHEN** the Report section renders
- **THEN** those structures are presented with accessible semantic HTML, readable spacing, and semantic strong text for the emphasized values
- **AND** Markdown control characters are not shown as ordinary report prose

#### Scenario: Copy exact Markdown

- **GIVEN** a formatted report is visible
- **WHEN** the user activates `Copy Markdown`
- **THEN** the clipboard receives the exact persisted Markdown content
- **AND** formatting the visible document has not mutated the artifact

#### Scenario: Render unsupported or hostile content safely

- **GIVEN** a persisted legacy report contains raw HTML, a Markdown link, malformed strong emphasis, or an unsupported construct
- **WHEN** the Report section renders
- **THEN** the content remains visible as inert text or safe fallback text
- **AND** no HTML executes and no active link or new analytical structure is created

### Requirement: Keep Summary result cards independently sized

The Summary section SHALL present availability/limitations and key findings as separate cards without stretching the availability/limitations card to match the height of a longer Key findings card. Each card SHALL retain its own content-driven height while preserving the existing responsive two-column layout and all availability, limitation, and finding content.

#### Scenario: Show short limitations beside many findings

- **GIVEN** a completed analysis has a short availability/limitations list and multiple long key findings
- **WHEN** the Summary section renders at a two-column viewport
- **THEN** the availability/limitations card ends after its own content and does not display unused warning-surface space below it
- **AND** Key findings remains visible in its independent card

### Requirement: Use meaning-oriented absence language in run analysis views

Completed Analysis and Report views SHALL describe empty findings, hypotheses, limitations, relationships, and optional evidence in terms of what the completed result contains or supports, not in terms of database persistence. Empty wording SHALL preserve the distinction between “none produced,” “not available,” and “execution not complete,” and SHALL NOT infer normality, absence of cause, or complete evidence coverage.

#### Scenario: Explain empty hypotheses after successful analysis

- **GIVEN** Observation analysis completed with findings and no hypotheses
- **WHEN** the Analysis section renders
- **THEN** it states that no knowledge-grounded possible explanation was produced
- **AND** it does not say that nothing was persisted or that no cause exists

#### Scenario: Keep unavailable distinct from empty

- **GIVEN** one run has completed analysis with an empty collection and another run has no analysis artifact
- **WHEN** each run detail renders
- **THEN** the first communicates a valid empty analytical result
- **AND** the second communicates unavailable analysis without treating it as empty or normal
