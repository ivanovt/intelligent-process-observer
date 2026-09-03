# alerts-analysis-pipeline Specification

## Purpose
Provide a deterministic, provider-transport-free internal pipeline that converts one
already-created Alert LensRun into a validated and durable AlertAnalysisResult while
keeping mandatory analysis separate from bounded Lens-local agent reasoning.

## Requirements

### Requirement: Analyze only an immutable existing Alert LensRun

The system SHALL analyze exactly one existing Alert LensRun that is already `running`.
The pipeline SHALL use its immutable Observation/Lens correlation, Alert Lens source,
opaque selector query, ordered configured reference offsets, analysis window, and
analysis timestamp. It SHALL NOT create ObservationRuns or LensRuns, mutate the Lens
definition, selector, time scope, reference configuration, or Observation scope.

#### Scenario: Analyze a prepared running Alert LensRun

- **GIVEN** a running Alert LensRun and its immutable Alert Lens execution context
- **WHEN** the internal Alerts Analysis Pipeline is invoked
- **THEN** all acquisition and analysis use that context
- **AND** the pipeline creates no top-level runtime object or new LensRun

#### Scenario: Reject a non-running Alert LensRun

- **GIVEN** an Alert LensRun that is not running
- **WHEN** the pipeline is invoked for it
- **THEN** the pipeline rejects the invocation before acquisition
- **AND** it does not create an AlertAnalysisResult

### Requirement: Acquire and validate current Alert records with lifecycle-overlap semantics

The system SHALL acquire current records through a provider-neutral Alert acquisition
boundary using the stored opaque selector and current analysis window. A current record
is in scope only when `started_at < window.end` and (`ended_at` is absent or
`ended_at > window.start`). The canonical usable record SHALL retain its provider ID,
title, lifecycle timestamps, source status, and available description, provider
importance, occurrence count, and source reference; it SHALL not retain raw provider
payload.

A record without an ID, title, or valid `started_at`, or with an `ended_at` before its
`started_at`, SHALL be rejected. Canonical Alert IDs SHALL be unique within every
normalized current or reference record set. Every record in a duplicate-ID collision
set SHALL be rejected as an invalid record rather than arbitrarily retained or merged.
A subset of rejected current records with at least one usable record SHALL leave the
pipeline usable but incomplete. If no usable current record remains after a successful
non-empty current response, the LensRun SHALL fail with `invalid_records`. A successful
empty current response SHALL remain a usable zero-record input. A duplicate collision
in a reference set follows the same invalid-record treatment for that reference and can
make only that reference unavailable.

#### Scenario: Include an alert spanning the window boundary

- **GIVEN** a returned alert starts before the current window ends and resolves after
  the current window begins
- **WHEN** current membership is evaluated
- **THEN** the alert is retained even when its start is before the window

#### Scenario: Continue with a usable subset

- **GIVEN** current acquisition returns both invalid records and at least one usable record
- **WHEN** normalization completes
- **THEN** rejected records are absent from evidence and the result
- **AND** the terminal usable result is partial with the selected primary reason

#### Scenario: Fail when every returned current record is invalid

- **GIVEN** a successful non-empty current response whose records are all invalid
- **WHEN** normalization completes
- **THEN** the LensRun becomes failed with `invalid_records`
- **AND** no AlertAnalysisResult is created

#### Scenario: Reject every duplicate current ID in its collision set

- **GIVEN** current normalization receives two or more otherwise valid records with the same canonical Alert ID
- **WHEN** canonical-ID uniqueness is validated
- **THEN** every colliding record is rejected as invalid rather than merged or selected
- **AND** the remaining usable subset follows the existing partial-or-failed `invalid_records` behavior

#### Scenario: Fail current acquisition distinctly

- **GIVEN** current acquisition returns an error or timeout before usable current data
- **WHEN** the pipeline maps the acquisition outcome
- **THEN** the LensRun becomes failed with respectively `current_query_failed` or `current_query_timeout`
- **AND** no AlertAnalysisResult is created

### Requirement: Derive independent reference evidence without exposing reference records

For each configured reference offset, the system SHALL derive a same-duration window
shifted backward by that offset and independently acquire, normalize, validate, and
analyze its records using the same selector and lifecycle-overlap rule. A successful
reference SHALL contribute only its deterministic occurrence comparison: current,
reference, delta, and `increased|decreased|unchanged` direction. The system SHALL not
serialize or expose raw reference records to the Alert Analysis Agent or
AlertAnalysisResult.

An unavailable, malformed, or wholly invalid reference SHALL omit only that offset's
comparison, retain all successful comparisons in configured-offset order, and create
the `reference_unavailable` incompleteness cause. It SHALL not make usable current
analysis fail or create a placeholder comparison.

#### Scenario: Retain successful comparisons around a failed offset

- **GIVEN** three configured offsets where the middle reference is unavailable
- **WHEN** reference processing completes
- **THEN** comparisons for the other successful offsets are retained in configured order
- **AND** the unavailable offset has no placeholder

#### Scenario: Keep zero-record current analysis reference-aware

- **GIVEN** current analysis has zero usable records and a configured reference succeeds
- **WHEN** the zero-record gate is reached
- **THEN** the successful comparison is retained before the agent is skipped

### Requirement: Produce mandatory deterministic alert evidence

The system SHALL deterministically produce current `alert_activity`, record-based
`status_distribution`, per-record lifecycle durations, duration statistics when at
least one record exists, optional provider-importance distribution, and successful
reference occurrence comparisons. It SHALL calculate effective occurrence count as the
provided count when present and `1` when absent; `record_count` SHALL count usable
records, while `occurrence_count` SHALL sum effective occurrence counts. Status counts
SHALL count records only.

For resolved records, duration SHALL be `ended_at - started_at`; for active records it
SHALL be `analysis_timestamp - started_at`. Durations and aggregate values SHALL be
finite non-negative JSON numbers in seconds. `average_seconds` SHALL be the unrounded
arithmetic mean of the record durations represented by the implementation's standard
finite numeric serialization. Provider importance SHALL preserve native type and
value without global severity mapping.

If mandatory deterministic evidence cannot be produced, the LensRun SHALL fail with
`deterministic_analysis_failed` and SHALL have no AlertAnalysisResult.

#### Scenario: Apply the missing occurrence default without changing status counts

- **GIVEN** one active record with no occurrence count and one resolved record with occurrence count `3`
- **WHEN** mandatory evidence is produced
- **THEN** record count is `2`, occurrence count is `4`, and each status count remains record-based

#### Scenario: Omit duration statistics for zero records

- **GIVEN** no usable current record
- **WHEN** mandatory evidence is produced
- **THEN** activity and zero-valued status distribution are present
- **AND** duration statistics are absent

### Requirement: Constrain Alert Analysis Agent and optional analysis

When `record_count` is greater than zero, the system SHALL invoke the mandatory Alert
Analysis Agent with only Lens name/description, normalized current records, mandatory
current evidence, and successful reference comparisons. The agent SHALL return only
deduplicated Lens-local descriptive findings and `overall_importance` of `low`,
`moderate`, `high`, or `critical`. It SHALL have no provider query, raw provider
payload, reference records, Metrics/Logs/Relationship evidence, RAG, external
knowledge, root-cause, recommendation, semantic-clustering, or scope-expansion
capability.

The Alert Analysis Agent completion SHALL be strict: `overall_importance` is exactly
one of `low|moderate|high|critical`, every finding has only its required well-formed
fields, and unknown or missing completion fields are invalid. An adapter or pipeline
boundary that receives malformed completion data, including `overall_importance=none`,
another invalid controlled value, an unknown or missing field, or malformed finding
structure, SHALL map it to `agent_failed`. It SHALL not pass such data to the result
builder and SHALL not create an AlertAnalysisResult.

The agent MAY invoke only recurrence concentration, duration outlier, and reference
pattern optional analyses over already-fetched run-local data. Every attempt,
including `success`, `not_applicable`, `failed`, and `timeout`, SHALL consume one of a
maximum of ten calls; repeated permitted tool use is allowed. `failed` and `timeout`
optional calls SHALL not alone make the LensRun partial or failed. Successful and
not-applicable optional outputs SHALL not be persisted as result sections; only a
minimal failed/timeout trace may be retained.

The recurrence tool SHALL calculate `top_record_share` as the largest effective
record-occurrence count divided by total occurrence count and return all tied top
record IDs in lexical order. It is not applicable when total occurrence count is zero.
The duration-outlier tool SHALL use the interpolated quartiles at indexes
`(n - 1) * 0.25` and `(n - 1) * 0.75` over ascending valid durations, a high-side
threshold of `Q3 + 1.5 * (Q3 - Q1)`, strict `duration > threshold`, and a minimum of
eight values. The reference-pattern tool SHALL require at least two successful
comparisons and return the unique most-frequent direction or `mixed` on a tie.

#### Scenario: Skip the agent only for zero records

- **GIVEN** mandatory evidence has `record_count=0` and any occurrence count
- **WHEN** the zero-record decision is made
- **THEN** the agent is not invoked
- **AND** findings are `[]` and overall importance is `none`

#### Scenario: Do not skip records with zero occurrences

- **GIVEN** mandatory evidence has `record_count>0` and `occurrence_count=0`
- **WHEN** the zero-record decision is made
- **THEN** the agent is invoked
- **AND** it cannot return `none` overall importance

#### Scenario: Reject an invalid agent completion before result building

- **GIVEN** a non-zero run whose agent completion has `overall_importance=none`, another invalid controlled value, an unknown or missing field, or malformed finding structure
- **WHEN** the adapter or pipeline validates the completion
- **THEN** the LensRun fails with `agent_failed`
- **AND** the result builder is not invoked and no AlertAnalysisResult is created

#### Scenario: Continue after an optional timeout

- **GIVEN** an agent optional-tool invocation times out before the tenth allowed call
- **WHEN** the agent continues with its remaining evidence and returns valid output
- **THEN** the LensRun status is unaffected by that timeout alone
- **AND** only the minimal timeout trace is eligible for the result

#### Scenario: Treat an undersized duration sample as normal non-applicability

- **GIVEN** the duration-outlier tool receives fewer than eight valid durations
- **WHEN** it evaluates the data
- **THEN** it returns `not_applicable`
- **AND** it creates no partial or failed status

### Requirement: Build a strict usable AlertAnalysisResult

The system SHALL build AlertAnalysisResult version `1.0` only after mandatory stages
succeed. Every completed or partial result SHALL contain the full runtime identity,
`lens_type="alert"`, status, analysis timestamp/window, provenance with source
provider and generated-at time, normalized current alerts, activity, status
distribution, comparisons, findings, and overall importance. Partial results SHALL
contain exactly one structured reason; completed results SHALL not contain one.

Every finding SHALL have a non-empty ID and statement and evidence references that
resolve to exactly one final-result target. The canonical evidence-reference grammar is
an ASCII URI with exact lowercase scheme `alert`, no userinfo/port, and one of these
complete forms:

```text
alert://current/{alert-id}
alert://aggregate/alert_activity/{record_count|occurrence_count}
alert://aggregate/status_distribution/{active|resolved|unknown}
alert://aggregate/duration_statistics/{min_seconds|max_seconds|average_seconds}
alert://aggregate/provider_importance/{importance-type}/{importance-value}
alert://comparison/{offset}
```

`alert-id`, `importance-type`, `importance-value`, and `offset` are dynamic URI path
segments. A dynamic value SHALL first be UTF-8 encoded; only RFC 3986 unreserved bytes
`A-Z a-z 0-9 - . _ ~` may remain literal, and every other byte SHALL use uppercase
`%HH` encoding. Thus a literal non-ASCII character, slash, space, percent sign, or a
percent-encoded unreserved byte is non-canonical. The URI SHALL reject malformed or
incomplete escapes, lowercase hexadecimal escape digits, invalid UTF-8 after decoding,
an empty dynamic segment, a query string, a fragment, or any missing, extra, or
otherwise different path segment. Static authorities and path segments are exact
lowercase literals; dynamic decoded values MUST exactly identify an existing target.

`alert://current/{alert-id}` resolves only to the one final `alerts[]` entry whose
canonical ID equals the decoded ID; current-ID uniqueness is enforced during
normalization and is rechecked by the builder. Aggregate forms resolve only to their
listed existing field; duration and provider-importance forms are unavailable when
their optional final-result sections are absent. A comparison form resolves only to the
one successful final comparison with the decoded configured offset. Findings based on
transient optional analysis SHALL reference only their underlying persisted records,
aggregates, or comparisons.

The builder SHALL receive only structurally valid agent output and SHALL reject a
reference that is non-canonical, malformed, ambiguous, or unresolvable, plus assembled
data with identity/provenance correlation inconsistencies, count/status/duration/
comparison invariant violations, or invalid final-section presence/omission. A builder
rejection SHALL fail the LensRun with `result_validation_failed/alert_result_builder`
and SHALL not create an artifact.

#### Scenario: Validate zero-record output

- **GIVEN** a successful zero-record path
- **WHEN** the result is built
- **THEN** it has `findings=[]`, `overall_importance=none`, and no duration statistics

#### Scenario: Resolve encoded reserved and Unicode current IDs canonically

- **GIVEN** a final current Alert ID containing reserved characters and Unicode text
- **WHEN** a finding uses its UTF-8 uppercase-percent-encoded `alert://current/{alert-id}` reference
- **THEN** the builder resolves it to exactly that one final record

#### Scenario: Reject a non-canonical or malformed evidence-reference URI

- **GIVEN** a structurally valid agent output containing a URI with a raw Unicode or reserved byte, lowercase or malformed percent escape, percent-encoded unreserved byte, invalid UTF-8, query, fragment, or wrong path shape
- **WHEN** the builder validates evidence references
- **THEN** the LensRun fails with `result_validation_failed/alert_result_builder`
- **AND** no AlertAnalysisResult is persisted

#### Scenario: Reject a non-resolving finding reference

- **GIVEN** a finding references an alert ID or comparison absent from the final result
- **WHEN** the builder validates evidence references
- **THEN** the LensRun fails with `result_validation_failed/alert_result_builder`
- **AND** no AlertAnalysisResult is persisted

### Requirement: Select one public reason and preserve Alert failure absence

The system SHALL produce a usable `partial` AlertAnalysisResult only for a usable
current deterministic core with some rejected current records and/or unavailable
references. When both incompleteness causes occur, it SHALL select one primary reason
with precedence `invalid_records` over `reference_unavailable`; components SHALL be
respectively `current_normalization` and `reference_periods`. Secondary causes and
per-offset/provider diagnostics SHALL remain operational only.

Current acquisition failure, all-invalid current records, mandatory deterministic
failure, malformed/contract-invalid required agent completion, required agent timeout,
and result-validation failure SHALL make the LensRun failed with their mapped reason.
Malformed/contract-invalid agent completion maps to `agent_failed`; final contextual or
assembled-result invariant failure maps to `result_validation_failed/alert_result_builder`.
A failed Alert LensRun SHALL have no AlertAnalysisResult, including an empty or
placeholder result.

#### Scenario: Select current-subset incompleteness over reference unavailability

- **GIVEN** usable current records remain after some are rejected and at least one configured reference is unavailable
- **WHEN** the terminal result is built
- **THEN** it is partial with `invalid_records/current_normalization`
- **AND** reference unavailability remains operational diagnostics

#### Scenario: Fail a non-zero run when the required agent fails

- **GIVEN** deterministic current evidence has records and the required Alert Analysis Agent errors, times out, or produces malformed completion data
- **WHEN** the agent outcome is mapped
- **THEN** the LensRun fails with `agent_failed` for errors or malformed completion, or `agent_timeout` for timeout
- **AND** no AlertAnalysisResult is created

### Requirement: Persist the terminal Alert outcome atomically through runtime persistence

The system SHALL use one caller-owned transaction to advance the running Alert LensRun
to its terminal status and, only for completed or partial outcomes, persist one
correlated validated AlertAnalysisResult through the existing runtime artifact
boundary. The result status and partial reason SHALL exactly match the LensRun. The
pipeline SHALL not create a new repository abstraction, table, migration, raw provider
payload store, or transient tool/model ledger store.

A flush or commit failure SHALL roll back both terminal state and artifact, propagate
the infrastructure/persistence failure, and SHALL not fabricate a terminal result.

#### Scenario: Persist a partial result with its matching LensRun reason

- **GIVEN** a validated partial AlertAnalysisResult and its running LensRun
- **WHEN** the caller-owned transaction persists the terminal outcome
- **THEN** the stored LensRun and result have matching `partial` status and structured reason

#### Scenario: Roll back a failed terminal write

- **GIVEN** terminal LensRun advancement and Alert result insertion are in one transaction
- **WHEN** flushing or committing that transaction fails
- **THEN** neither terminal transition nor artifact is durable
- **AND** the failure is surfaced as infrastructure failure

### Requirement: Keep provider transport and production model selection outside the pipeline capability

The pipeline capability SHALL consume injected provider and agent boundaries. It SHALL
not contain a Jira Track and Release endpoint, API field mapping, transport,
authentication, credentials, retry/backoff policy, pagination/truncation policy,
production model or provider selection, provider-specific model settings, or external
live calls. A separately specified Jira Alert provider MAY implement those concerns
behind the existing injected AlertProvider port; it SHALL not alter the pipeline's
provider-neutral acquisition, normalization, analytical, agent, result, or persistence
contracts. The existing PydanticAI dependency, where used, SHALL remain in an
infrastructure adapter behind the framework-neutral agent boundary.

#### Scenario: Exercise the pipeline without live integrations

- **GIVEN** deterministic fake provider and agent implementations
- **WHEN** the pipeline contract is exercised in tests
- **THEN** current/reference, agent, result, and persistence behavior is verifiable
- **AND** no Jira credential, network transport, or production model configuration is required

#### Scenario: Supply a production provider without changing pipeline semantics

- **GIVEN** a separately configured Jira provider is injected through AlertProvider
- **WHEN** it returns an existing typed acquisition outcome for an immutable window
- **THEN** the pipeline applies the same current/reference outcome and normalization
  rules as for a fake provider
- **AND** Jira transport details remain outside the pipeline capability
