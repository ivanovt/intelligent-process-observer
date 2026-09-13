## ADDED Requirements

### Requirement: Let operators explicitly control an Observation knowledge scope

The Create and Edit Observation flows SHALL expose an optional Knowledge scope field in the
client-side Observation draft. It SHALL allow an operator to add or remove canonical service IDs
and set or clear one optional service-version label. The review step SHALL show the accepted scope
as knowledge-retrieval context, not as Lens evidence, an execution setting, a source selector, or
a causal assertion. The field SHALL be submitted only with the final aggregate create or
replacement request.

#### Scenario: Apply an explicit scope to the Observation draft
- **GIVEN** an operator enters service `mprm-server` and version `2.x` in Knowledge scope
- **WHEN** the operator proceeds to review and creates the Observation
- **THEN** the displayed and submitted aggregate includes that knowledge scope
- **AND** no standalone scope resource or Lens configuration is created

### Requirement: Offer only operator-initiated LLM scope suggestions

The Knowledge scope field SHALL include an accessible, clearly labelled suggestion control using a
non-semantic AI-assistance icon. It SHALL invoke suggestion only after the operator explicitly
activates that control; editing an Observation, Lens, description, objective, or scope SHALL not
make an automatic model request.

For an initiated request, the backend SHALL provide the model only the current Observation name,
description, objective, Lens names/descriptions, and derived approved service catalog. The model
SHALL return either zero suggestions or only canonical service IDs present in that supplied
catalog. It SHALL not receive document passages, embeddings, operational evidence, provider data,
or existing run results. A suggestion SHALL be advisory, visibly distinct from an applied scope,
and shall not include a service version unless the operator enters one.

Accepting a suggestion SHALL populate the local draft only; rejecting or ignoring it SHALL have no
effect. A missing, ambiguous, failed, or stale suggestion SHALL not block draft validation, submit
a scope, expose model diagnostics, or trigger a corpus search from the browser.

#### Scenario: Accept an operator-initiated service suggestion
- **GIVEN** current draft text is eligible for the approved service catalog's `mprm-server` ID
- **WHEN** the operator activates Suggest knowledge scope and accepts the returned suggestion
- **THEN** `mprm-server` is added to the local Knowledge scope draft
- **AND** it is persisted only if the final Observation aggregate is submitted

#### Scenario: Return no suggestion without blocking the draft
- **GIVEN** the model cannot identify a sufficiently supported catalog service from the current
draft or suggestion execution fails safely
- **WHEN** the operator activates Suggest knowledge scope
- **THEN** the UI reports that no scope suggestion is available without model diagnostic detail
- **AND** the operator may still enter an explicit scope or leave it empty

#### Scenario: Discard a stale suggestion
- **GIVEN** a scope suggestion request is pending for one draft revision
- **WHEN** the operator changes relevant Observation or Lens text before it completes
- **THEN** the returned suggestion is not displayed or applied to the newer draft revision
- **AND** the operator can initiate a new suggestion explicitly
