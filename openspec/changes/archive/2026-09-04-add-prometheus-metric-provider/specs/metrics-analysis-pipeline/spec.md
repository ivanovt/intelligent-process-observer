## MODIFIED Requirements

### Requirement: Acquire metric series only through the internal provider boundary

The pipeline SHALL depend on a framework-neutral single-series provider port accepting the immutable provider address and an exact requested window. It SHALL use that port for current and reference acquisition and SHALL NOT depend on Prometheus HTTP/client types, implement transport authentication/retry, or choose source configuration. Application composition MAY select and inject the separately specified production Prometheus provider implementation behind that unchanged port.

Each configured reference window SHALL have the current window's duration and be shifted backward by its exact positive configured offset. An explicit empty offset list SHALL cause no reference request and SHALL receive no default.

#### Scenario: Acquire zero configured references

- **GIVEN** `reference_periods=[]`
- **WHEN** the pipeline acquires Metric data
- **THEN** it requests only the current window
- **AND** it creates no default reference or `previous_period`

#### Scenario: Acquire one configured reference

- **GIVEN** one configured offset
- **WHEN** the pipeline acquires references
- **THEN** it requests one equal-duration window shifted backward by that exact offset
- **AND** it keeps current and reference series distinct

#### Scenario: Acquire multiple references independently

- **GIVEN** multiple ordered configured offsets
- **WHEN** the pipeline acquires references
- **THEN** each request and outcome remains attributable to exactly one offset
- **AND** no offset is interpreted as a baseline, normality definition, or automatic seasonality class

#### Scenario: Test without provider transport

- **GIVEN** a fake satisfies the provider port
- **WHEN** the pipeline is tested
- **THEN** all current/reference behavior is executable without Prometheus HTTP, credentials, retries, or a provider SDK

### Requirement: Persist terminal Metric outcome atomically through the existing repository

The pipeline SHALL use one caller-owned transaction to advance the existing LensRun to its terminal `completed|partial|failed` state and persist at most one correlated validated Metric artifact. It SHALL use the existing runtime repository/artifact table and SHALL NOT create another Metric result persistence model.

An analytical failure that produces a valid minimal failed Metric result SHALL persist that failed LensRun and traceability artifact atomically. A flush or commit failure SHALL roll back both terminal state and artifact, propagate an infrastructure/persistence error, and SHALL NOT claim terminal persistence or fabricate another result. Recovery/retry SHALL remain with the later execution/orchestration capability.

The existing repository SHALL receive only the bounded read operation required for D9 History candidate loading. No raw telemetry, provider payload, prompt trajectory, or transient tool ledger SHALL be persisted.

#### Scenario: Round-trip all Metric result variants

- **GIVEN** validated completed-sufficient, completed-insufficient, partial, and minimal failed Metric results
- **WHEN** each is persisted and retrieved through the existing artifact boundary
- **THEN** strict payload absence/presence, identity, status, reason, window, and provenance round-trip without normalization

#### Scenario: Roll back persistence failure

- **GIVEN** terminal LensRun advancement and artifact insertion are in one caller-owned transaction
- **WHEN** flush or commit fails
- **THEN** both writes roll back
- **AND** an infrastructure/persistence error is surfaced without fabricated terminal persistence

#### Scenario: Avoid transport, model, and framework coupling

- **GIVEN** the completed feature is inspected
- **WHEN** its production modules and dependencies are reviewed
- **THEN** Prometheus runtime transport and source selection appear only in infrastructure/composition behind the provider-neutral Metric port
- **AND** the Metric domain and pipeline remain free of Prometheus HTTP/client types, while PydanticAI remains only in the agent infrastructure adapter
