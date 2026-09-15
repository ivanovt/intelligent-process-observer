## ADDED Requirements

### Requirement: Recover relevant passages from an over-constrained lexical query

For each admitted curated-knowledge retrieval call, the system SHALL first apply the existing strict lexical and semantic relevance admission over the metadata-eligible corpus. Only when that initial hybrid admission produces no passage SHALL the retriever evaluate a deterministic relaxed lexical fallback within the same call. The fallback SHALL derive its terms only from the original finding-grounded query and SHALL NOT invoke a model, broaden the knowledge scope, fetch another source, or consume another reasoning retrieval slot.

A passage admitted by the relaxed fallback SHALL match at least two distinct normalized query terms and SHALL also meet a separate server-owned semantic-distance ceiling. Relaxed lexical rank, semantic distance, and minimum distinct-term count SHALL be fixed server-owned policy. Neither lexical ranking alone, semantic nearest-neighbor position alone, nor a single shared query term SHALL make a passage relevant. If no candidate meets either the initial admission or all relaxed-admission conditions, the call SHALL return the existing successful empty batch.

Strict and relaxed results SHALL retain the existing deterministic ranking, complete-passage serialization, source-version/chunk provenance, maximum of four passages, 8,192-byte serialized batch bound, and shared 30-second full-call deadline.

#### Scenario: Recover scoped knowledge for a verbose finding-grounded query
- **GIVEN** an approved scope-compatible passage directly describes the condition represented by frozen findings
- **AND** verbose peripheral wording causes the initial strict hybrid admission to produce no passage
- **AND** the passage matches at least two distinct normalized query terms and meets the relaxed semantic-distance ceiling
- **WHEN** the admitted retrieval call executes
- **THEN** the relaxed fallback admits the passage as candidate knowledge within that same call
- **AND** its exact retained source-version and chunk reference are preserved

#### Scenario: Preserve an admitted strict result
- **GIVEN** the initial strict lexical or semantic admission produces one or more passages
- **WHEN** the admitted retrieval call executes
- **THEN** the retriever returns the bounded strict-path result without activating relaxed admission
- **AND** relaxed matching does not add or reorder candidates

#### Scenario: Reject a weak relaxed lexical coincidence
- **GIVEN** initial strict admission produces no passage
- **AND** an otherwise eligible passage shares only one normalized query term or does not meet the relaxed semantic-distance ceiling
- **WHEN** the relaxed fallback is evaluated
- **THEN** that passage is not returned
- **AND** nearest-neighbor position or lexical rank alone does not override the failed condition

#### Scenario: Preserve an empty successful result
- **GIVEN** approved eligible passages exist but none satisfies the initial admission or every relaxed-admission condition
- **WHEN** the admitted retrieval completes successfully
- **THEN** it returns an empty retrieved batch
- **AND** it does not fabricate knowledge, broaden scope, or consume a second reasoning retrieval slot

#### Scenario: Keep fallback work inside existing resource bounds
- **GIVEN** relaxed evaluation is required for an admitted retrieval call
- **WHEN** query embedding, strict search, relaxed search, ranking, and serialization execute
- **THEN** all work shares the existing 30-second full-call deadline
- **AND** the result still contains at most four complete passages and at most 8,192 UTF-8 bytes
