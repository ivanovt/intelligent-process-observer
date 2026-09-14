## ADDED Requirements

### Requirement: Browse Metric Lens outcomes within one run

The Run Detail `Metrics` section SHALL show one selectable item for every Metric LensRun in the loaded durable run-detail response, including pending, running, completed, partial, failed, cancelled, and completed-insufficient outcomes. It SHALL show the total Metric LensRun count without describing every outcome as analyzed. On first load with at least one Metric LensRun, it SHALL select the first item in response order and show exactly one item's detail at a time. The selected item SHALL be visibly and programmatically identified; users SHALL be able to dismiss its detail and select another item. At narrow widths, the same list and detail SHALL remain usable in sequence without horizontal clipping or loss of information. An empty Metric collection SHALL retain the run-detail empty-state meaning.

#### Scenario: Compare mixed outcomes

- **GIVEN** a run detail contains completed, partial, and failed Metric LensRuns
- **WHEN** the Metrics section opens
- **THEN** all three appear in response order, the first is selected, and the count is three Metric Lenses
- **AND** the failed Lens remains selectable without being described as successfully analyzed

#### Scenario: Select and dismiss detail

- **WHEN** the user selects another Metric LensRun and then dismisses the detail
- **THEN** only the selected Lens's detail is shown before dismissal, and no detail is shown afterward
- **AND** the list remains available for a new selection

#### Scenario: Use the Metrics section at a narrow width

- **WHEN** the Metrics section is viewed at a narrow viewport
- **THEN** every Lens item can be selected and its full detail can be read in a stacked layout
- **AND** no evidence is hidden solely because the side-by-side layout does not fit

### Requirement: Summarize each Metric Lens without overstating its evidence

Each Metric list item SHALL display its Lens execution status and available start time and duration as separate operational information. When a Metric result supplies frozen `metric_ref` and unit, those SHALL be the primary measurement identity and the exact Lens ID SHALL remain accessible as secondary traceability. If no result is available, the Lens ID SHALL identify the item without fetching a mutable Observation Definition or inventing a Lens name. A usable good/degraded result SHALL show data quality, mandatory current trend direction/rate and variability, and a compact numerical summary from its accepted current evidence. Completed-insufficient, failed, cancelled, pending, and running outcomes SHALL explain why current semantic or numerical evidence is unavailable instead of rendering a fabricated state or zero. Partial results SHALL show their usable current evidence alongside the supported limitation/reason. Status, quality, and semantic cues SHALL use text as well as color.

#### Scenario: Scan a usable partial result

- **GIVEN** a partial Metric result has good current data, increasing/moderate trend, high variability, and reason `reference_unavailable`
- **WHEN** its list item renders
- **THEN** Partial, data quality good, current trend and variability, and available numerical evidence remain distinct
- **AND** the reference limitation is visible without recasting the Lens as failed or the current evidence as unavailable

#### Scenario: Scan a failed Metric result

- **GIVEN** a failed Metric LensRun has a failed Metric artifact with frozen identity and a safe failure reason
- **WHEN** its item renders
- **THEN** it shows Failed, the available frozen identity, and the safe reason
- **AND** it shows no data-quality success badge, current-state descriptor, or numerical value

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

The Metrics section SHALL use the existing run-detail refresh and active-run polling behavior. On each successful response, it SHALL present that response's coherent durable snapshot and preserve the selected Lens by stable LensRun ID while that ID remains present; if the selected ID is absent, it SHALL fall back to the first returned Metric LensRun or no selection. It SHALL display a last-updated label for the latest successful client refresh rather than the Metric result generation time. A failed refresh with previously loaded data SHALL keep that data and selected Lens visible with explicit stale-data feedback. A selected-Lens action to the existing run-level Analysis section SHALL be labelled `View Observation analysis` and SHALL NOT imply a separate Lens-only analysis. The Metrics detail SHALL NOT show Time series, Logs, or JSON tabs, nor expose provider queries, raw samples, operational logs, or internal diagnostics.

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

#### Scenario: Open the run-level analysis

- **WHEN** the user activates `View Observation analysis` from a selected Metric Lens
- **THEN** the existing Analysis section of the same Observation run opens
- **AND** the action does not claim that the Analysis section is a Lens-local result
