# curated-knowledge-retriever Specification

## Purpose
Supply bounded reasoning with traceable passages from the approved curated corpus while preserving
the existing evidence-first and framework-neutral knowledge-retrieval boundaries.

## Requirements

### Requirement: Retrieve only approved, applicable curated knowledge

For an admitted existing knowledge-retrieval request, the production retriever SHALL search only
the active approved version of each retained knowledge document. It SHALL exclude imported,
deprecated, failed, and unavailable versions. It SHALL admit globally applicable documents and,
when the Observation has an explicit knowledge scope, documents tagged with at least one matching
canonical service ID. Where both the Observation scope and a matching document tag provide a
version label, the document SHALL be eligible only when the tag contains the exact opaque scope
version; when the Observation scope omits a version, all matching service tags are eligible
regardless of their version labels. An unversioned matching tag remains eligible. When an
Observation has no knowledge scope, only globally applicable approved documents are eligible.

Within the eligible set, retrieval SHALL combine lexical matching with semantic vector similarity
and return a bounded ranked set of extracted passages. Ranking alone SHALL not make a passage
relevant: every returned passage SHALL first meet a server-owned lexical or semantic relevance
admission rule, and the retriever SHALL return an empty valid batch when none does. It SHALL not
broaden the Observation scope, fetch a source, or use model-internal knowledge.

One admitted retrieval call SHALL return at most four complete passages. Its entire serialized
model-visible retrieval batch, including statements and references, SHALL be at most 8 KiB
(8,192 UTF-8 bytes); passage text SHALL not be truncated to meet this bound. Approved chunks SHALL
be sized so one retrieved item can fit within the batch bound. Query embedding, database search,
ranking, and result serialization SHALL share one 30-second per-call deadline. These bounds are
server-owned and SHALL not be enlarged by the Observation, operator, or model. The existing
maximum of two sequential retrieval calls remains unchanged.

#### Scenario: Retrieve a service-applicable passage
- **GIVEN** an Observation has knowledge scope service `mprm-server` and an approved matching
runbook section relevant to its frozen finding
- **WHEN** the reasoning hypothesis phase performs an admitted retrieval
- **THEN** the retriever may return that runbook section as candidate knowledge
- **AND** it excludes an otherwise similar document applicable only to another service

#### Scenario: Limit an unscoped Observation to global knowledge
- **GIVEN** an Observation has no explicit knowledge scope and approved global and
service-specific documents exist
- **WHEN** an admitted retrieval executes
- **THEN** only globally applicable documents are eligible
- **AND** service-specific documents do not become candidates from textual similarity alone

#### Scenario: Include a version-tagged document when the scope has no version
- **GIVEN** an Observation scope names service `mprm-server` without a version, and an approved
  document tags `mprm-server` version `2.x`
- **WHEN** an admitted retrieval executes
- **THEN** the document is eligible alongside other matching-service and global documents
- **AND** its version tag does not exclude it until the Observation supplies a version

#### Scenario: Return no passage for an unrelated query
- **GIVEN** approved eligible documents exist but none meets the relevance admission rule for a
  finding-grounded query
- **WHEN** an admitted retrieval executes
- **THEN** it returns an empty valid batch
- **AND** the nearest vector neighbor is not presented as explanatory knowledge merely because
  it ranks first

#### Scenario: Enforce the MVP passage and context bounds
- **GIVEN** more than four relevant eligible passages are available
- **WHEN** one admitted retrieval completes
- **THEN** it returns no more than four complete passages whose serialized model-visible batch is
  at most 8,192 UTF-8 bytes
- **AND** it does not truncate a cited passage or extend the existing two-call budget

### Requirement: Preserve source-version and location provenance

Every retrieved knowledge item SHALL preserve the exact accepted framework-neutral knowledge
reference shape while identifying the retained document and immutable version that supplied it. Its
reference SHALL identify one immutable approved chunk within that version. The version's retained
chunk metadata SHALL resolve a PDF reference to a one-based page number and page-local chunk
ordinal, or a Markdown reference to a document-local chunk ordinal and its stored heading path.
PDF heading detection SHALL not be required or treated as authoritative. The returned statement
SHALL be extracted source text, not a model-authored summary. A later document import, approval,
deprecation, or source disappearance SHALL not alter the provenance of an already persisted
hypothesis.

#### Scenario: Cite an approved PDF passage without a section heading
- **GIVEN** a retrieved item comes from the third retained chunk on PDF page 12, with no reliable
  section heading
- **WHEN** reasoning forms a valid knowledge-grounded hypothesis from that item
- **THEN** the hypothesis retains a reference to the exact document identity, approved version,
  page 12, and its third page-local chunk
- **AND** the reference remains resolvable after a later document version is approved

#### Scenario: Resolve a Markdown heading without relying on its text as an identifier
- **GIVEN** a retrieved Markdown chunk has a retained heading path that is duplicated elsewhere
- **WHEN** a hypothesis cites its immutable document-local chunk ordinal
- **THEN** the reference resolves to that exact chunk and stored heading path
- **AND** duplicate heading text does not make the reference ambiguous

### Requirement: Preserve retrieval failure outcomes distinct from no matches

An admitted search SHALL return an empty successful batch only when it completes and no passage
meets eligibility and relevance admission. An embedding timeout SHALL retain the existing
`timed_out` outcome; an embedding, database, or index failure SHALL retain the existing `failed`
outcome. Such failures SHALL not be converted into a successful empty result or a fabricated
knowledge item. The composition-time empty fallback remains the separate production policy for
unavailable knowledge infrastructure before a run.

Exceeding the 30-second full-call deadline SHALL produce the existing `timed_out` outcome, including
when the delay occurs after query embedding during database search or result construction.

#### Scenario: Distinguish no match from provider failure
- **GIVEN** an admitted retrieval has eligible passages but its query-embedding provider fails
- **WHEN** the bounded retrieval executor handles the request
- **THEN** it records a `failed` outcome through its existing safe failure contract
- **AND** it does not report a successful empty search

#### Scenario: Distinguish no match from timeout
- **GIVEN** an admitted retrieval exceeds its embedding deadline
- **WHEN** the bounded retrieval executor handles the request
- **THEN** it records a `timed_out` outcome through its existing safe timeout contract
- **AND** no passage or fabricated knowledge reference is returned

#### Scenario: Time out the complete retrieval call
- **GIVEN** query embedding succeeds but database search exceeds the remaining 30-second call budget
- **WHEN** the bounded retrieval executor handles the request
- **THEN** it records a `timed_out` outcome without a partial knowledge batch
- **AND** a second call, if requested, remains subject to the existing two-call session budget

### Requirement: Disclose approved source text to the configured embedding provider only

When an operator explicitly approves a document version, the system SHALL send extracted approved
document text to the configured OpenRouter embedding endpoint. When an admitted retrieval executes,
it SHALL send only its bounded finding-grounded query text to that endpoint. It SHALL disclose
before approval that approved document text is externally processed and that later bounded
finding-grounded retrieval queries are also externally processed. It SHALL not send original file
bytes, raw telemetry, provider payloads, credentials, or user-facing API payloads as embedding
input.

#### Scenario: Confirm external embedding processing before publication
- **GIVEN** an imported document version is ready for approval
- **WHEN** an operator opens its approval confirmation
- **THEN** the UI states that extracted document text and later bounded finding-grounded retrieval
queries will be sent to OpenRouter to create embeddings
- **AND** embedding begins only after the operator confirms approval

### Requirement: Keep curated knowledge untrusted and separate from observed evidence

Retrieved document text, metadata, and aliases SHALL be treated as untrusted knowledge data. They
SHALL not create or modify findings, determine overall state, expand a provider or Lens scope,
become a recommendation, or automatically select an Observation knowledge scope. Existing
retrieval call budgets, frozen-finding grounding, hypothesis validation, and failure semantics
remain unchanged.

The optional Observation knowledge scope SHALL be bound to the run's retriever only. It SHALL not
be included in the finding-formation or overall-state model inputs, and it SHALL not be treated as
evidence by the hypothesis model.

#### Scenario: Prevent retrieved text from creating a finding
- **GIVEN** a runbook claims that a particular logging pattern commonly signals a dependency outage
- **WHEN** its passage is retrieved during hypothesis formation
- **THEN** the system may use it only for a cited possible explanation of frozen findings
- **AND** it does not add a dependency-outage finding or change the overall state

#### Scenario: Keep knowledge scope out of evidence-only model inputs
- **GIVEN** an Observation run has an explicit service knowledge scope
- **WHEN** finding formation and overall-state determination are invoked
- **THEN** neither model input contains that knowledge scope
- **AND** the retriever still uses the frozen scope to filter its candidates
