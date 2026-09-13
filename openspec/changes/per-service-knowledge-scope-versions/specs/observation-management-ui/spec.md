## MODIFIED Requirements

### Requirement: Let operators explicitly control an Observation knowledge scope

The Create and Edit Observation flows SHALL expose an optional Knowledge scope in the client-side Observation draft. The operator SHALL be able to add or remove canonical service entries and independently set or clear one optional service-version label on each entry. The version control SHALL be visibly associated with its own service; adding, removing, or editing another service SHALL not copy or change that label. The review step SHALL show every service beside its own version or an explicit no-version state as knowledge-retrieval context, not as Lens evidence, an execution setting, a source selector, or a causal assertion. The field SHALL be submitted only with the final aggregate create or replacement request.

An accepted scope suggestion SHALL add only catalog-backed service IDs to the local draft with no version labels. It SHALL not replace an operator-entered version for an already selected service or assign a version to another service. The operator SHALL enter any desired version explicitly.

#### Scenario: Apply a different version to each service in the draft
- **GIVEN** an operator selects `mprm-server` with version `1.0` and `gateway` without a version
- **WHEN** the operator reviews and creates the Observation
- **THEN** the review and submitted aggregate show `1.0` only beside `mprm-server` and no version beside `gateway`
- **AND** no standalone scope resource or Lens configuration is created

#### Scenario: Editing one service does not change another service's version
- **GIVEN** the draft contains two services with different version choices
- **WHEN** the operator clears one service's version or removes that service
- **THEN** the other service and its version remain unchanged

#### Scenario: Accept a suggestion without inventing versions
- **GIVEN** an operator has entered a version for one selected service
- **WHEN** the operator accepts a suggestion for another service
- **THEN** the suggested service is added without a version
- **AND** the existing service keeps its operator-entered version
