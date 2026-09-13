## MODIFIED Requirements

### Requirement: Use an explicit empty KnowledgeRetriever until knowledge integration exists

Production Observation Reasoning SHALL receive the curated-corpus KnowledgeRetriever when the
curated knowledge persistence/index is available. The adapter SHALL implement the existing
framework-neutral KnowledgeRetriever port and SHALL return only approved, applicable, provenance-
preserving retrieved items under the existing bounded retrieval session. It SHALL not expose
database, embedding, vector-store, extraction, document-management, or provider types to
reasoning contracts.

When curated knowledge infrastructure is unavailable at application composition time, production
SHALL inject a safe unavailable retriever that returns an empty validated item collection for every
admitted request. It SHALL not fabricate KnowledgeReferences, retrieved statements, hypotheses,
diagnostics, or a hidden local knowledge source. A transient retrieval failure SHALL retain the
existing typed retrieval failure semantics and SHALL not make application startup fail or change
Observation execution lifecycle behavior.

The existing bounded retrieval and reasoning rules SHALL remain unchanged. A model MAY request
retrieval and observe an empty result; any final hypothesis SHALL still require accepted knowledge
references, so unavailable or empty retrieval cannot support a fabricated hypothesis.

#### Scenario: Retrieve curated approved knowledge
- **GIVEN** the curated corpus is available and Observation Reasoning has formed one or more
findings
- **WHEN** its model requests knowledge retrieval
- **THEN** production delegates through the existing framework-neutral port to the curated retriever
- **AND** any returned item has the exact retained source provenance required by existing hypothesis
validation

#### Scenario: Retrieve with no production knowledge backend
- **GIVEN** curated knowledge infrastructure cannot be composed at application startup
- **WHEN** Observation Reasoning requests knowledge retrieval
- **THEN** the production retriever returns an empty validated collection without diagnostic detail
- **AND** findings and overall analytical state may still be produced under their existing contracts

#### Scenario: Complete reasoning without knowledge hypotheses
- **GIVEN** retrieval returns no knowledge items
- **WHEN** Observation Reasoning completes successfully
- **THEN** findings and overall analytical state may still be produced under their existing contracts
- **AND** no hypothesis without knowledge references is accepted
