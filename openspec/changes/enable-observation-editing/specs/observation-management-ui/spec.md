## MODIFIED Requirements

### Requirement: Place management in the Observations product area
The system SHALL present Observation management under the existing `Observations` navigation area using the accepted UI shell, hierarchy, terminology, and restrained engineering-dashboard visual language. It SHALL provide routes for the definitions list, read-only definition inspection, aggregate creation, aggregate editing, and nested Metric Lens, Alert Lens, and Relationship editors without exposing a separate Admin area.

The management capability SHALL NOT expose monitoring/run-analysis screens, Observation delete controls, standalone Lens lifecycle controls, Log Lens configuration, dark-mode controls, or unsupported agent, model, prompt, tool-budget, severity, confidence, recommendation, or runtime-relationship configuration.

#### Scenario: Enter Observation management
- **WHEN** a user selects `Observations` in the application navigation
- **THEN** the Observation definitions list is shown within the shared ObserveAI shell
- **AND** no separate Admin navigation area is present

#### Scenario: Keep later UI out of scope
- **WHEN** a user navigates through the Observation Management flow
- **THEN** the UI exposes only definition list, read-only definition inspection, aggregate creation and editing, and the three supported nested configuration editors
- **AND** it does not expose Observation deletion, monitoring, or run-analysis screens

### Requirement: List, search, and inspect supported definition data
The system SHALL load existing definitions from `GET /api/v1/observations` and SHALL provide case-insensitive client-side substring search over the returned `name` and optional `description` only. Observation ID, objective, Lens data, and Relationship data SHALL NOT participate in search. Each row SHALL show the Observation name, available descriptive text, Metric Lens count, Alert Lens count, Relationship count, and distinct `Open` and `Edit` actions using only fields returned by the definition API.

The list SHALL NOT show or filter by latest runtime timestamp, analytical state, execution state, duration, or other runtime data because the current list contract does not provide them. It SHALL NOT expose Delete actions. `Open` SHALL retrieve `GET /api/v1/observations/{observation_id}` and present a read-only definition inspection view within the Observations product area; this view SHALL NOT imply that a monitoring/run detail view has been implemented. The inspection view SHALL also offer an `Edit Observation` action for the loaded identity.

#### Scenario: Search loaded definitions
- **GIVEN** the list API has returned Observation summaries
- **WHEN** the user enters search text
- **THEN** the displayed definitions are filtered locally by case-insensitive substring match against name and description without inventing a server-side search endpoint

#### Scenario: Search has no matches
- **GIVEN** the list API succeeded with a non-empty collection
- **WHEN** no returned name or description matches the search text
- **THEN** the UI presents a distinct no-matching-definitions state with a way to clear the search
- **AND** does not present the collection-level empty state

#### Scenario: Open a definition
- **WHEN** the user activates `Open` for a listed definition
- **THEN** the UI loads the complete definition through its supported read endpoint
- **AND** presents its metadata, Metric Lenses, Alert Lenses, and Relationships as read-only configuration data
- **AND** offers an Edit action for that definition

#### Scenario: Edit a listed definition
- **WHEN** the user activates `Edit` for a listed definition
- **THEN** the UI enters the aggregate edit route for that Observation identity
- **AND** loads the complete definition before presenting editable values

#### Scenario: Definition inspection is loading
- **WHEN** a user opens a listed definition or directly visits its read-only route and the detail request is pending
- **THEN** the UI presents an explicit loading state within the Observations product area
- **AND** does not present an empty or valid definition

#### Scenario: Definition is not found
- **WHEN** the detail endpoint returns `404 Not Found` for the requested Observation identity
- **THEN** the UI presents a distinct not-found state with a way to return to the definitions list
- **AND** does not present an empty or valid definition

#### Scenario: Definition inspection fails
- **WHEN** the detail request fails for a reason other than not found
- **THEN** the UI presents an explicit error state with retry and back-to-list actions
- **AND** retry requests the same Observation identity again
- **AND** the failure is not presented as an empty or valid definition

#### Scenario: Omit unsupported lifecycle and runtime controls
- **WHEN** the list is rendered from the current definition summaries
- **THEN** it shows no Delete actions and no latest-runtime columns or filters

## ADDED Requirements

### Requirement: Initialize and cancel one persisted aggregate edit draft

The edit flow SHALL retrieve the complete definition from `GET /api/v1/observations/{observation_id}` and initialize one client-side draft containing its exact mutable domain values and collection order. The Observation identity, schema version, API links, runtime state, and runtime artifacts SHALL remain outside the editable payload. Persisted child IDs SHALL be retained exactly and SHALL remain non-editable.

The flow SHALL distinguish loading, `404 Not Found`, and retryable load failure before showing the form. Cancelling the top-level edit flow SHALL discard all local changes and return to the read-only definition without an HTTP write. Refreshing or directly entering a nested edit route without the matching initialized draft SHALL return to the parent edit route, reload the persisted definition, and explain that unapplied local changes were unavailable.

#### Scenario: Initialize an edit draft
- **WHEN** the edit detail request succeeds
- **THEN** General fields and every Metric Lens, Alert Lens, and Relationship are editable from a draft matching the canonical definition and its collection order
- **AND** no write occurs during initialization

#### Scenario: Cancel the aggregate edit
- **GIVEN** the user has changed metadata or draft children
- **WHEN** the user cancels the top-level edit flow
- **THEN** no update request is sent
- **AND** the read-only definition route is shown with its last persisted values

#### Scenario: Fail to initialize editing
- **WHEN** loading the target definition returns not found or another failure
- **THEN** the UI presents the corresponding not-found or retryable error state
- **AND** does not present a neutral or partially initialized edit form

#### Scenario: Enter a nested edit route without its draft
- **WHEN** a user refreshes or directly visits a nested editor under an Observation edit route without its matching live draft
- **THEN** the UI returns to the parent edit route and reloads the persisted aggregate
- **AND** explains that unapplied local changes were not retained
- **AND** sends no write request

### Requirement: Fully edit aggregate-owned configuration in one draft

The edit flow SHALL permit changing all mutable fields supported by the current definition contract: Observation `name`, optional `description`, `objective`; every Metric Lens field; every Alert Lens field; and every Relationship field. It SHALL permit adding, editing, removing, and reordering Metric Lenses, Alert Lenses, and Relationships while maintaining at least one Lens overall and all current validation and topology rules.

Nested `Apply changes` SHALL update only the client draft and return to the parent edit flow without an HTTP write. Cancelling or navigating back from a nested editor SHALL leave the parent draft unchanged. Removing an owned child SHALL require an explicit user action in the parent draft and SHALL not issue a standalone child request. Removing a Metric Lens SHALL also make any Relationship that references it invalid until the user repairs or removes that Relationship; the UI SHALL not silently rewrite Relationship rules.

An existing child's ID SHALL remain unchanged when its fields are edited. A newly added child SHALL use the accepted generated-ID behavior. The edit flow SHALL explain that a stable Metric Lens ID retains identity-scoped History, while removing a Metric Lens and adding a new one establishes a fresh identity.

#### Scenario: Edit every supported configuration type
- **GIVEN** a persisted mixed Observation
- **WHEN** the user changes General fields and applies revisions to a Metric Lens, Alert Lens, and Relationship
- **THEN** the parent draft contains all revised values under their existing child IDs
- **AND** no write occurs before final save

#### Scenario: Add, remove, and reorder owned children
- **WHEN** the user adds a child, explicitly removes an existing child, and changes collection order
- **THEN** the draft represents the desired complete aggregate snapshot in that order
- **AND** no standalone child create, update, or delete request occurs

#### Scenario: Cancel nested edits
- **GIVEN** the user changes an existing or new child in a nested editor
- **WHEN** the user cancels or navigates back without applying
- **THEN** the parent edit draft remains unchanged
- **AND** no HTTP write occurs

#### Scenario: Expose a broken Relationship after Metric removal
- **GIVEN** an existing Relationship references a Metric Lens
- **WHEN** the user removes that Metric Lens from the draft
- **THEN** aggregate validation identifies the affected Relationship for repair or removal
- **AND** the UI does not silently remove the participant or alter its conditions or expectations

#### Scenario: Communicate Metric History identity
- **GIVEN** the user edits a persisted Metric Lens
- **WHEN** its existing ID is retained
- **THEN** the UI communicates that future runs retain History continuity for that Lens identity
- **AND** offers removal and creation of a new Lens as the path to a fresh identity

### Requirement: Validate and save one aggregate replacement

Before final save, the edit flow SHALL validate the same represented aggregate invariants as creation and SHALL retain the draft when validation fails. Final `Save changes` SHALL construct the complete supported mutable aggregate payload, exclude identity, schema version, links, UI-only state, and runtime data, and send exactly one `PUT /api/v1/observations/{observation_id}` request. It SHALL send no child write requests.

On `200 OK`, the UI SHALL clear the edit draft, confirm that the Observation was updated, and open the returned canonical definition in read-only form. API field errors SHALL be associated with represented General or nested fields when possible and otherwise shown as an aggregate error. A `404 Not Found` during save SHALL report that the target no longer exists and SHALL not imply creation or partial persistence. Any other failed save SHALL retain the complete draft for correction or retry.

#### Scenario: Block an invalid edit locally
- **GIVEN** the edit draft violates a represented Observation, Lens, or Relationship invariant
- **WHEN** the user activates `Save changes`
- **THEN** no update request is sent
- **AND** accessible summary, field, and section-level errors are presented while the draft is retained

#### Scenario: Save an edited definition
- **GIVEN** a valid edit draft
- **WHEN** the user activates `Save changes`
- **THEN** the UI sends exactly one aggregate replacement request to the edited Observation identity and no child write requests
- **AND** on `200 OK` it clears the draft, confirms success, and opens the returned definition

#### Scenario: Preserve the draft after update rejection
- **WHEN** the update API returns a validation or transport failure
- **THEN** the UI presents actionable field or aggregate feedback without implying partial persistence
- **AND** retains the complete draft for correction or retry

#### Scenario: Target disappears before save
- **WHEN** the update API returns `404 Not Found`
- **THEN** the UI explains that the Observation is no longer available
- **AND** does not retry as a create request or claim that any changes were saved
