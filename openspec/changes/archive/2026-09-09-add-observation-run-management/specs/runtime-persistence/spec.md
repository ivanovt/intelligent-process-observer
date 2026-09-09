## ADDED Requirements

### Requirement: Enforce one active ObservationRun per Observation

Runtime persistence SHALL prevent more than one ObservationRun whose status is `pending` or `running` from existing for the same `observation_id`, including when launch attempts race across transactions within the supported single-process application host. The enforcement SHALL NOT restrict concurrent active runs belonging to different Observations and SHALL NOT restrict the number of immutable terminal historical runs for one Observation. It SHALL NOT claim cross-process task ownership or make multi-process startup reconciliation safe.

#### Scenario: Race two active-run inserts

- **GIVEN** no active run exists for an Observation
- **WHEN** two transactions concurrently try to initialize a run for that Observation
- **THEN** at most one active ObservationRun commits
- **AND** the losing transaction leaves no parent, LensRun, or artifact residue

#### Scenario: Preserve terminal history

- **GIVEN** an Observation has multiple terminal historical runs
- **WHEN** a new run is initialized
- **THEN** the new active run can commit without modifying or deleting the terminal runs

### Requirement: Retrieve complete runtime history deterministically

Runtime persistence SHALL retrieve all ObservationRuns in descending creation order with stable run-identity tie-breaking and SHALL support resolving the Observation identity and display name needed by the public list projection. It SHALL retrieve one run by stable identity with its ordered LensRuns and all correlated persisted Lens analyses, RelationshipEvaluations, ObservationAnalysisResult, and ObservationReport artifacts where present.

One detail retrieval SHALL observe one coherent PostgreSQL database snapshot across every query needed to assemble the aggregate. A concurrent terminal lifecycle/artifact transaction SHALL therefore be visible either entirely before or entirely after the detail snapshot, never as a torn combination such as a stale LensRun status paired with its newly committed result. The full-history summary projection SHALL obtain each response from one statement-level durable snapshot.

Full-history retrieval SHALL return no pagination cursor or truncation. It SHALL distinguish an absent optional artifact from a present artifact whose collection fields are empty and SHALL preserve execution status independently from any available Observation analytical state.

#### Scenario: Retrieve newest-first history

- **GIVEN** runs exist for multiple Observations at different creation times
- **WHEN** complete runtime history is retrieved
- **THEN** every run is returned exactly once in newest-first order
- **AND** equal creation positions are ordered deterministically by run identity

#### Scenario: Retrieve an active run without analytical artifacts

- **GIVEN** an ObservationRun is pending or running and has not produced Observation analysis or a report
- **WHEN** its detail aggregate is retrieved
- **THEN** lifecycle, analysis-window, LensRun, and available artifact data are returned
- **AND** the missing ObservationAnalysisResult and ObservationReport remain explicitly absent

#### Scenario: Retrieve analysis from a failed run

- **GIVEN** a run persisted ObservationAnalysisResult but later failed during report generation
- **WHEN** list or detail data is retrieved
- **THEN** execution status remains `failed`
- **AND** the independently persisted analytical state remains available without being overwritten or inferred

#### Scenario: Interleave a terminal write with detail retrieval

- **GIVEN** detail retrieval has begun and a concurrent transaction atomically terminalizes a LensRun with its artifact
- **WHEN** the detail aggregate finishes loading
- **THEN** it contains either the pre-commit running LensRun without that artifact or the post-commit terminal LensRun with that artifact
- **AND** it never combines lifecycle and artifact values from different database snapshots

### Requirement: Reconcile active records left by process interruption

Before accepting public launches, runtime persistence SHALL atomically transition every recovered `pending` or `running` LensRun to `cancelled` with reason `execution_cancelled`, preserve every already terminal LensRun and committed artifact, and transition each recovered active ObservationRun to `cancelled` with the same reason. The same operation SHALL support recovery after a detached persistence failure by reconciling all active records owned by the sole supported process after its managed tasks have been quiesced.

Reconciliation SHALL be idempotent and SHALL NOT resume, delete, or fabricate artifacts for interrupted work. Runtime reconciliation SHALL begin only after the manager confirms every initializer and continuation from the fenced older generation has settled and closed its database transaction/session scope. An uncertain initializer SHALL never be retried. A reconciliation transaction failure SHALL propagate and SHALL NOT clear the manager's `recovery_required` state or startup readiness gate. Successful reconciliation SHALL be followed by durable verification that no `pending|running` ObservationRun remains before launch admission resumes.

#### Scenario: Reconcile after an ungraceful stop

- **GIVEN** persisted active runtime records have no owning execution task after process restart
- **WHEN** startup reconciliation runs
- **THEN** all unfinished records become durably cancelled in one coherent operation per ObservationRun
- **AND** the active-run uniqueness rule no longer blocks a fresh execution

#### Scenario: Repeat startup reconciliation

- **GIVEN** a previous startup already reconciled all orphaned active records
- **WHEN** reconciliation runs again
- **THEN** terminal records and artifacts remain byte-for-byte unchanged in their domain values

#### Scenario: Reconciliation cannot commit

- **GIVEN** active records require cancellation and persistence is unavailable
- **WHEN** reconciliation fails to commit
- **THEN** active records are not reported as durably terminalized
- **AND** launch admission and startup readiness remain blocked

#### Scenario: Defer reconciliation until initialization settles

- **GIVEN** an older-generation initializer has an indeterminate commit outcome and its session scope is still closing
- **WHEN** recovery is requested
- **THEN** persistence reconciliation waits until that admission settles
- **AND** its final active-state query cannot be followed by a late commit from that initializer

#### Scenario: Restore admission after verified reconciliation

- **GIVEN** the manager entered recovery after detached persistence uncertainty
- **WHEN** reconciliation commits and a durable verification read finds no active ObservationRun
- **THEN** the manager may return to `ready`
- **AND** later explicit launches create fresh runtime identities rather than retrying interrupted work

### Requirement: Persist RelationshipEvaluation definition order

Every RelationshipEvaluation persisted for an ObservationRun SHALL carry a zero-based non-negative ordinal equal to its Relationship's position in the frozen ordered definition snapshot. Ordinals SHALL be unique within one ObservationRun and SHALL form the exact contiguous range `0..N-1` for the atomically persisted evaluation batch. The ordinal is persistence ordering metadata and SHALL NOT add a field or schema version to the domain-owned RelationshipEvaluation payload.

Retrieval SHALL order RelationshipEvaluations by this persisted ordinal and SHALL NOT reconstruct order from UUID, timestamp, insertion accident, lexical Relationship ID, or the current mutable definition. Existing rows migrated by this change SHALL derive their ordinal by joining their ObservationRun to the current immutable MVP Relationship definition with the same `relationship_id`; migration SHALL abort without rewriting those artifacts if any row cannot resolve uniquely or would produce duplicate/non-contiguous order.

#### Scenario: Persist an ordered evaluation batch

- **GIVEN** a frozen Observation snapshot contains three Relationships in definition order
- **WHEN** their validated evaluation batch is persisted atomically
- **THEN** the rows receive unique ordinals `0`, `1`, and `2` matching that order
- **AND** their domain payloads remain unchanged

#### Scenario: Retrieve order independently of row metadata

- **GIVEN** RelationshipEvaluation row UUIDs, creation timestamps, or physical insertion order differ from definition order
- **WHEN** run detail is retrieved
- **THEN** evaluations are returned by persisted ordinal
- **AND** no current definition lookup is required to reconstruct their order

#### Scenario: Abort an unresolvable legacy backfill

- **GIVEN** an existing RelationshipEvaluation cannot map uniquely to a current Relationship definition position
- **WHEN** the ordinal migration runs
- **THEN** migration aborts with an actionable non-secret error
- **AND** it does not guess an ordinal, delete the row, or alter its analytical payload
