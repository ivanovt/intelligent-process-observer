## Purpose

Offer an operator-initiated, constrained LLM suggestion for optional Observation knowledge scope
without automatically applying scope metadata or exposing the curated document corpus.

## ADDED Requirements

### Requirement: Suggest only catalog-backed service scope on explicit request

The system SHALL expose a trusted-MVP backend operation that accepts a transient Observation draft
projection containing only name, optional description, objective, and Lens names/descriptions. It
SHALL invoke a server-owned LLM only after an explicit operator request and only when the derived
approved service catalog is non-empty. The model input SHALL contain the draft projection and
canonical service IDs with their approved aliases; it SHALL contain no document bytes, extracted
passages, embeddings, source locations, Observation runs, provider data, credentials, agent
prompts, or execution configuration.

The typed model result SHALL contain either an empty suggestion or unique canonical service IDs
selected exclusively from the supplied catalog. It SHALL not produce a service version, a
recommendation, a finding, a hypothesis, an analytical state, confidence/probability/severity, or
free-form rationale. The operation SHALL not persist any part of the draft or suggestion, run
retrieval, or alter the corpus.

#### Scenario: Return a catalog-backed service suggestion
- **GIVEN** the approved catalog contains `mprm-server` and the submitted draft describes its
matching component
- **WHEN** an operator explicitly requests a knowledge-scope suggestion
- **THEN** the response may contain `mprm-server` and no identifier absent from the catalog
- **AND** no Observation Definition or knowledge document is persisted or changed

#### Scenario: Return no suggestion for insufficient context
- **GIVEN** the submitted draft cannot support a catalog-backed service choice
- **WHEN** an operator explicitly requests a knowledge-scope suggestion
- **THEN** the response contains an empty suggestion
- **AND** it contains no model rationale, confidence, or diagnostic detail

### Requirement: Fail safely without automatic retry or scope mutation

The system SHALL return a safe unavailable suggestion outcome when the server-side model is
unavailable, times out, violates the typed suggestion policy, or returns invalid output. It SHALL
not reveal credential state, provider/model details, prompt content, model output, exception text,
or stack traces. It SHALL not retry automatically, persist a fallback service ID, or make any
change to the Observation draft or approved service catalog.

#### Scenario: Handle an unavailable suggestion model
- **GIVEN** a trusted operator explicitly requests a suggestion while the model integration is
unavailable
- **WHEN** the request completes
- **THEN** the response signals that no suggestion is available without sensitive diagnostic detail
- **AND** the operator may continue with an explicit scope or no scope
