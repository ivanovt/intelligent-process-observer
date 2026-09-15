## ADDED Requirements

### Requirement: Record safe curated-knowledge retrieval decisions

After each successfully completed curated-knowledge retrieval search, the backend SHALL emit one correlated informational operational event that distinguishes `strict_admitted`, `relaxed_admitted`, and `no_match`. The event SHALL include only available run correlation, the selected controlled strategy category, and bounded aggregate counts for strict candidates, strict admissions, relaxed candidates, relaxed admissions, and returned passages. Counts for a path that was not evaluated SHALL be represented consistently without implying that the path ran.

The event SHALL NOT contain query text or terms, passage or document text, embeddings, lexical ranks, semantic distances, knowledge source identifiers, provider details, model messages, or credentials. Emission or serialization failure SHALL NOT alter the retrieval outcome, analytical result, runtime lifecycle, or public API response.

#### Scenario: Explain a successful relaxed retrieval safely
- **GIVEN** initial admission is empty and the relaxed fallback returns one or more passages
- **WHEN** the retrieval call completes successfully
- **THEN** one correlated informational event identifies `relaxed_admitted` and its bounded aggregate counts
- **AND** the event contains no query, content, score, distance, source, embedding, provider, or credential value

#### Scenario: Explain a successful no-match result safely
- **GIVEN** neither initial nor relaxed admission returns a passage
- **WHEN** the retrieval call completes successfully
- **THEN** one correlated informational event identifies `no_match` with zero returned passages and bounded aggregate decision counts
- **AND** the existing successful empty retrieval outcome remains unchanged

#### Scenario: Preserve retrieval when diagnostics fail
- **GIVEN** retrieval has selected a valid non-empty or empty result
- **WHEN** the diagnostic event cannot be serialized or emitted
- **THEN** retrieval returns the selected result unchanged
- **AND** no failure, limitation, hypothesis, or lifecycle transition is introduced by the diagnostic problem
