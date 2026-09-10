## Purpose

Provide the production Observation Management experience for finding, inspecting, drafting, validating, and creating Observation Definitions while preserving aggregate ownership and the current public API boundaries.

## Requirements

### Requirement: Place management in the Observations product area
The system SHALL present Observation management under the existing `Observations` navigation area using the accepted UI Direction v1.3 shell, hierarchy, terminology, and restrained engineering-dashboard visual language. It SHALL provide routes for the definitions list, read-only definition inspection, aggregate creation, and nested Metric Lens, Alert Lens, and Relationship editors without exposing a separate Admin area.

The management capability SHALL NOT expose monitoring/run-analysis screens, Observation update/delete controls, standalone Lens lifecycle controls, Log Lens configuration, dark-mode controls, or unsupported agent, model, prompt, tool-budget, severity, confidence, recommendation, or runtime-relationship configuration.

#### Scenario: Enter Observation management
- **WHEN** a user selects `Observations` in the application navigation
- **THEN** the Observation definitions list is shown within the shared ObserveAI shell
- **AND** no separate Admin navigation area is present

#### Scenario: Keep later UI out of scope
- **WHEN** a user navigates through the Observation Management flow
- **THEN** the UI exposes only definition list, read-only definition inspection, aggregate creation, and the three supported nested configuration editors
- **AND** it does not expose monitoring or run-analysis screens

### Requirement: List, search, and inspect supported definition data
The system SHALL load existing definitions from `GET /api/v1/observations` and SHALL provide case-insensitive client-side substring search over the returned `name` and optional `description` only. Observation ID, objective, Lens data, and Relationship data SHALL NOT participate in search. Each row SHALL show the Observation name, available descriptive text, Metric Lens count, Alert Lens count, Relationship count, and an `Open` action using only fields returned by the definition API.

The list SHALL NOT show or filter by latest runtime timestamp, analytical state, execution state, duration, or other runtime data because the current list contract does not provide them. It SHALL NOT expose Edit or Delete actions. `Open` SHALL retrieve `GET /api/v1/observations/{observation_id}` and present a read-only definition inspection view within the Observations product area; this view SHALL NOT imply that a monitoring/run detail view has been implemented.

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
- **THEN** it shows no Edit or Delete actions and no latest-runtime columns or filters

### Requirement: Provide explicit list loading, error, and empty states
The definitions list SHALL distinguish loading, failed loading, an empty collection, and a successful collection. A failed request SHALL offer a retry action and SHALL NOT imply that no Observations exist or that any process is analytically normal.

#### Scenario: Load an empty collection
- **WHEN** the list API succeeds with an empty collection
- **THEN** the UI presents an explicit empty state with a `New Observation` action

#### Scenario: Fail to load definitions
- **WHEN** the list API request fails
- **THEN** the UI presents an error state and retry action
- **AND** does not present the failure as an empty or analytically normal state

### Requirement: Maintain one local Observation aggregate draft
The create flow SHALL maintain one client-side Observation draft containing distinct `name`, optional `description`, `objective`, ordered Metric `lenses`, ordered `alert_lenses`, and ordered `relationships`. General, Metric lenses, Alert lenses, Relationships, and Review SHALL be presented as sections of that one aggregate flow.

Opening a nested editor SHALL create editor-local working state. `Cancel`, browser back from the editor, or dismissal SHALL return to Create Observation without mutating the aggregate draft. `Apply changes` SHALL validate the editor-local value, commit it to the appropriate draft collection, and return to Create Observation. `Apply changes` SHALL make no HTTP write request. Cancelling the top-level create flow SHALL discard the draft and return to the definitions list.

#### Scenario: Cancel nested edits
- **GIVEN** a user changes values in a nested Lens or Relationship editor
- **WHEN** the user cancels the editor
- **THEN** the Observation draft remains byte-for-byte equivalent in its domain values to the state before the editor opened

#### Scenario: Apply nested edits
- **GIVEN** a nested editor contains a valid new or revised child configuration
- **WHEN** the user activates `Apply changes`
- **THEN** that child is added to or replaced in the local Observation draft at its intended ordered position
- **AND** no Observation, Lens, or Relationship API write occurs

#### Scenario: Cancel the aggregate draft
- **GIVEN** the user has populated General data and one or more draft children
- **WHEN** the user cancels the top-level Create Observation flow
- **THEN** the entire local aggregate draft is discarded and the definitions list is shown
- **AND** a subsequent Create Observation flow starts with a neutral draft

#### Scenario: Enter a nested editor without a live draft
- **WHEN** a user directly visits or refreshes a nested Metric Lens, Alert Lens, or Relationship editor route without a live aggregate draft
- **THEN** the UI redirects to `/observations/new` and presents neutral draft-loss feedback
- **AND** the resulting Create Observation flow contains a neutral draft
- **AND** no draft mutation or HTTP write request occurs


### Requirement: Generate stable IDs for new Observation children
The Metric Lens, Alert Lens, and Relationship editors SHALL generate the new child's ID when the user leaves its name field after entering a non-whitespace name and the child does not already have an ID. The generated ID SHALL have the exact composition `<type-prefix>_<normalized-name>_<random-part>` and SHALL match the public identifier syntax `^[a-z][a-z0-9_-]*$`. Metric Lens IDs SHALL use `metr`, Alert Lens IDs SHALL use `alrt`, and Relationship IDs SHALL use `rel` as their type prefix. The random part SHALL contain eight lowercase hexadecimal characters generated from browser-provided randomness. The complete ID SHALL NOT exceed 255 characters.

Name normalization SHALL apply Unicode NFKD decomposition, remove Unicode combining marks, convert the result to lowercase, replace each sequence of remaining characters outside ASCII `a-z0-9` with one underscore, and remove leading and trailing underscores. When normalization produces no leading ASCII lowercase letter, the normalized-name segment SHALL fall back to `item`. The UI SHALL truncate only the normalized-name segment as needed to keep the complete generated ID within 255 characters; it SHALL preserve the type prefix and random part.

The generated value SHALL avoid a duplicate among the relevant current draft collection. Metric IDs SHALL be compared only with other Metric IDs, Alert IDs only with other Alert IDs, and Relationship IDs only with other Relationship IDs; the backend contract's allowance for cross-type Lens ID equality SHALL remain unchanged. If the initial random candidate already exists, the UI SHALL append `_2` and increment the numeric discriminator until the candidate is unique. For every collision attempt, it SHALL further truncate only the normalized-name segment as needed to preserve the type prefix, random part, complete discriminator, identifier syntax, and 255-character maximum.

The editors SHALL NOT present the child ID as an input or other editable form control. Once generated, the ID SHALL appear as secondary non-editable text adjacent to the Name field identity, formatted as `(id: <generated-id>)` and exposed as text to assistive technology. Before generation, the Name field guidance SHALL explain that the ID is generated after the initial non-empty name is entered. Once a new child receives an ID, later name edits SHALL NOT regenerate or otherwise change it. Reopening an already-applied draft child SHALL display and preserve its existing ID exactly, including an ID created before this typed format was introduced. ID generation and editor cancellation SHALL make no HTTP write and SHALL not mutate the aggregate draft until `Apply changes` succeeds.

#### Scenario: Generate a Metric Lens ID from its initial name
- **GIVEN** a new Metric Lens has no ID
- **WHEN** the user enters `Cooling Pressure` as its name and leaves the name field
- **THEN** the editor displays secondary identity text matching `(id: metr_cooling_pressure_<random-part>)`
- **AND** the random part contains eight lowercase hexadecimal characters
- **AND** the generated ID satisfies the public identifier syntax
- **AND** no separate Lens ID input is present

#### Scenario: Generate IDs with each child type prefix
- **WHEN** the UI generates IDs for a Metric Lens, an Alert Lens, and a Relationship
- **THEN** their IDs begin with `metr_`, `alrt_`, and `rel_` respectively
- **AND** each ID retains the normalized-name and random components

#### Scenario: Keep a generated ID stable after renaming
- **GIVEN** a new child has received a generated ID
- **WHEN** the user changes its name and leaves the name field again
- **THEN** the generated ID remains unchanged
- **AND** the secondary identity text continues to show that unchanged value

#### Scenario: Preserve an existing draft child ID
- **GIVEN** an already-applied Metric Lens, Alert Lens, or Relationship is reopened for editing
- **WHEN** its editor is displayed or its name is changed
- **THEN** its existing ID remains unchanged even when it does not use the new typed prefix
- **AND** the existing ID is presented as secondary non-editable identity text rather than an input

#### Scenario: Generate a valid fallback ID
- **GIVEN** a new Alert Lens has no ID
- **WHEN** the user enters a non-whitespace name whose normalization has no leading lowercase Latin letter and leaves the name field
- **THEN** the generated ID matches `alrt_item_<random-part>`
- **AND** it satisfies the public identifier syntax

#### Scenario: Normalize decomposable Latin diacritics consistently
- **GIVEN** a new Relationship has no ID
- **WHEN** the user enters `Crème Pressure` as its name and leaves the name field
- **THEN** the generated ID begins with `rel_creme_pressure_`
- **AND** the remaining random part contains eight lowercase hexadecimal characters

#### Scenario: Bound an ID generated from a long name
- **GIVEN** a new child has a name whose normalized-name segment would make the generated ID longer than 255 characters
- **WHEN** the name is committed
- **THEN** the UI truncates the normalized-name segment
- **AND** the generated ID preserves its complete type prefix and random part, satisfies the public identifier syntax, and is at most 255 characters long

#### Scenario: Avoid a same-collection collision
- **GIVEN** the relevant draft collection already contains the initial generated candidate
- **WHEN** a new child receives the same normalized name and random part
- **THEN** the editor displays a distinct valid ID produced by adding or incrementing a numeric discriminator
- **AND** any required additional normalized-name truncation keeps the complete ID at most 255 characters long

#### Scenario: Preserve type-local Lens identity
- **GIVEN** existing persisted or draft Metric and Alert Lenses use equal legacy IDs
- **WHEN** the UI displays or submits those existing values
- **THEN** it preserves both IDs unchanged
- **AND** the backend identifier grammar and type-local uniqueness behavior remain unchanged

#### Scenario: Leave the ID empty for a blank name
- **GIVEN** a new child has no ID
- **WHEN** the user leaves a name field containing only whitespace
- **THEN** no ID is generated or displayed
- **AND** the Name guidance explains when generation occurs
- **AND** the existing required-name validation remains applicable

#### Scenario: Cancel after local ID generation
- **GIVEN** a nested editor has generated an ID in editor-local state
- **WHEN** the user cancels the editor
- **THEN** the aggregate Observation draft remains unchanged
- **AND** no HTTP write request is made

### Requirement: Resolve Metric capabilities without blocking Alert-only creation
The system SHALL obtain available Metric adapter/source choices from `GET /api/v1/observation-definition-capabilities` and SHALL distinguish pending, retryable request failure, a successful response with no Metric sources, and a successful response with supported sources. While capabilities are pending or unavailable, the Metric editor SHALL NOT invent a source or allow a Metric Lens to be applied with unresolved acquisition configuration.

A failed or empty Metric capability response SHALL affect only Metric Lens configuration. The user SHALL remain able to cancel the Metric editor and create a valid Alert-only Observation. A failed capabilities request SHALL provide retry; a successful empty response SHALL explain that no Metric source is configured.

#### Scenario: Load available Metric sources
- **WHEN** the capabilities request succeeds with one or more supported Metric sources
- **THEN** the Metric editor offers exactly those adapter/source choices

#### Scenario: Capabilities request fails
- **WHEN** the capabilities request fails
- **THEN** the Metric editor presents an error and retry action and prevents Metric Apply
- **AND** the rest of the aggregate flow, including Alert-only creation, remains usable

#### Scenario: No Metric source is configured
- **WHEN** the capabilities request succeeds with an empty Metric capability set
- **THEN** the Metric editor presents a no-configured-source explanation and prevents Metric Apply
- **AND** does not invent or retain a default source
- **AND** Alert-only creation remains usable

### Requirement: Configure Metric Lenses against the current public contract
The Metric Lens editor SHALL capture and map `id`, `name`, optional `description`, exact `type: metric`, `metric_id`, exact supported `adapter_type`, `source_id`, provider-native `query`, `unit`, ordered `analysis_objectives`, and ordered `reference_periods`. Available adapter/source choices SHALL come from `GET /api/v1/observation-definition-capabilities`; the UI SHALL NOT invent sources or a metric catalog.

One Metric Lens SHALL describe exactly one metric. Metric objectives SHALL use the shared inline ordered objective interaction but SHALL constrain submitted values to the current API vocabulary `spike`, `drift`, and `oscillation`, reject duplicates, and preserve selected order. The UI SHALL identify unrestricted Metric objective text as a backend dependency rather than submitting unsupported values. Reference offsets SHALL match `^[1-9][0-9]*(m|h|d|w)$`, reject duplicates, and preserve configured order.

Persisted-history controls shown in the frozen mock SHALL be omitted or disabled with an explicit backend-dependency explanation because the current public definition contract has no history-policy field. Reference periods SHALL not be represented as persisted history. No analyzer or tool toggles SHALL be exposed.

#### Scenario: Apply a valid Metric Lens
- **WHEN** the user applies a valid Metric Lens editor value
- **THEN** the draft receives one `lenses` item matching the current Metric Lens create shape and preserving objective and reference-period order

#### Scenario: Prevent unsupported Metric configuration
- **WHEN** the user configures Metric objectives or history behavior
- **THEN** only the three current objective values can enter the submitted draft
- **AND** no history-policy, analyzer-selection, tool-selection, or unsupported free-text objective field enters the payload

#### Scenario: Preserve type-local Lens identity
- **GIVEN** an Alert Lens already uses an ID that is not used by another Metric Lens
- **WHEN** the user applies a Metric Lens with that same ID
- **THEN** the editor accepts the cross-type duplicate

### Requirement: Configure Alert Lenses as owned opaque-selector data
The Alert Lens editor SHALL capture and map `id`, exact `type: alert`, non-whitespace `name`, optional non-whitespace `description`, exact supported `source: jira_track_and_release`, `selector.query`, ordered `analysis_objectives`, and ordered `reference_periods` into the parent draft.

The selector query SHALL be treated as opaque provider-native input and preserved exactly as entered. The UI SHALL validate only that it contains non-whitespace content; it SHALL NOT trim, parse, normalize, lint, rewrite, or add time or lifecycle-status predicates. Alert objectives SHALL use the shared inline editor, reject blank or duplicate exact values, and preserve configured order. Reference offsets SHALL use the Metric offset syntax, reject duplicates, and preserve configured order.

#### Scenario: Preserve an opaque selector
- **WHEN** a user applies an Alert Lens whose non-whitespace selector includes provider-specific spacing or syntax
- **THEN** the draft and final aggregate payload contain the exact selector string entered by the user

#### Scenario: Apply ordered Alert values
- **WHEN** a valid Alert Lens with multiple objectives and reference offsets is applied
- **THEN** the draft preserves the configured order of both lists without adding defaults

#### Scenario: Keep Alert Lens aggregate-owned
- **WHEN** the user applies an Alert Lens
- **THEN** it is stored only in the draft's `alert_lenses` collection
- **AND** no standalone Alert Lens create, update, or delete request is made

### Requirement: Configure constrained Metric-only Relationships
The Relationship editor SHALL capture and map a unique Relationship `id`, non-empty `name`, optional `description`, an ordered list of 2..N distinct Metric Lens participant IDs, Lens-keyed `conditions`, and non-empty Lens-keyed `expected` descriptors. Participant choices SHALL resolve only against the current draft's Metric `lenses`; an Alert Lens with the same ID SHALL not satisfy or create ambiguity for a participant.

Every participant SHALL be referenced by at least one condition or expectation. Conditions MAY be empty to represent an always-applicable Relationship, while expectations SHALL be non-empty. The editor SHALL expose only `trend.direction` values `increasing | decreasing | stable`, `trend.rate` values `slow | moderate | fast`, and `variability.state` values `low | moderate | high`. It SHALL represent descriptors through explicit participant/property/value controls and SHALL NOT provide a generic expression DSL or free-form rule engine.

#### Scenario: Apply a conditional Relationship
- **GIVEN** at least two Metric Lenses exist in the draft
- **WHEN** the user applies a Relationship whose participants and When/Expect descriptors satisfy the accepted vocabulary and topology
- **THEN** the draft receives the corresponding `relationships` item using Lens-ID-keyed `conditions` and `expected` maps

#### Scenario: Apply an always-applicable Relationship
- **WHEN** a valid Relationship has no conditions and has at least one expectation
- **THEN** the editor accepts it with an empty `conditions` map

#### Scenario: Reject an Alert participant
- **WHEN** a user attempts to select an Alert Lens as a Relationship participant
- **THEN** the editor prevents that selection or rejects the configuration before draft mutation

### Requirement: Validate the aggregate and submit exactly once
Before final submission, the UI SHALL validate all represented public-contract invariants and SHALL present field and aggregate errors without removing the user's draft. At minimum it SHALL require non-empty Observation `name` and `objective`, at least one Metric or Alert Lens overall, unique IDs within each Lens type, unique Relationship IDs, valid child shapes and ordered-list values, and Relationships that resolve only to draft Metric Lenses with valid topology and vocabulary. Cross-type equality between one Metric Lens ID and one Alert Lens ID SHALL remain allowed.

Final `Create Observation` SHALL construct the existing `ObservationCreate` payload with `name`, `description`, `objective`, `lenses`, `alert_lenses`, and `relationships`, excluding UI-only and runtime state, and SHALL send exactly one `POST /api/v1/observations`. The backend SHALL remain authoritative: API validation errors SHALL be associated with the returned field when possible and otherwise shown as an aggregate error without silently rewriting the payload.

#### Scenario: Block an invalid aggregate locally
- **GIVEN** the draft violates a represented Observation, Lens, or Relationship invariant
- **WHEN** the user attempts final creation
- **THEN** no create request is sent
- **AND** actionable validation errors are presented while the draft is retained

#### Scenario: Create successfully
- **GIVEN** a valid aggregate draft
- **WHEN** the user activates final `Create Observation`
- **THEN** the UI sends exactly one aggregate create request and no child write requests
- **AND** on `201 Created` it clears the draft, confirms success, and opens the returned definition in read-only form

#### Scenario: Preserve draft after create failure
- **GIVEN** a valid local draft
- **WHEN** the create API fails or rejects the payload
- **THEN** the UI presents the failure without implying partial persistence
- **AND** retains the draft so the user can correct or retry it

### Requirement: Communicate the active Create Observation configuration section
The system SHALL visually distinguish exactly one active item in the Create Observation configuration navigation. It SHALL expose the active item to assistive technology without changing the Observation draft, nested-editor lifecycle, or aggregate submission behavior.

#### Scenario: Open or return to the top of Create Observation
- **WHEN** the Create Observation page is initially shown at its top or the user scrolls back to the top
- **THEN** `General` is the active configuration item
- **AND** no other configuration item is marked active

#### Scenario: Activate a configuration navigation item
- **WHEN** the user activates `General`, `Metric lenses`, `Alert lenses`, `Relationships`, or `Review` in the configuration navigation
- **THEN** that item is immediately marked active
- **AND** the page navigates to its existing corresponding section anchor

#### Scenario: Scroll through configuration sections
- **WHEN** the user scrolls so a different configuration section becomes the current leading section in the viewport
- **THEN** the corresponding configuration item becomes the sole active item

#### Scenario: Reach the bottom of the aggregate form
- **WHEN** the user reaches the bottom of the Create Observation page where the Review section concludes the form
- **THEN** `Review` is the active configuration item

#### Scenario: Expose active state accessibly
- **WHEN** a configuration item is active
- **THEN** its navigation link exposes the current-location state to assistive technology
- **AND** inactive links do not expose that state

### Requirement: Present layered and accessible form validation feedback
The system SHALL present blocking validation feedback at both a concise form summary and the affected control or configuration group after an invalid `Create Observation` or nested `Apply changes` attempt. Invalid controls SHALL be visually distinguishable by more than color alone, SHALL retain their persistent guidance, and SHALL remain programmatically associated with their error messages.

When multiple validation problems appear together, the system SHALL announce and focus one validation summary rather than announcing every field error independently. The summary SHALL state the number of issues and provide actionable links to affected fields or sections where those targets are available. Presenting validation feedback SHALL NOT mutate or discard the Observation draft.

Continuously computed Review feedback before a Create attempt SHALL be presented as neutral or incomplete draft guidance rather than as submitted blocking errors. Blocking summaries, invalid-control treatments, and navigation issue counts SHALL derive only from the latest explicit Create, Apply, or field-specific API validation result. After a user edits a value, those displayed blocking issues SHALL remain until the next explicit validation replaces them.

#### Scenario: Reject an invalid Create Observation attempt
- **WHEN** a user activates `Create Observation` and represented aggregate validation fails
- **THEN** the UI focuses a validation summary that states how many issues need attention
- **AND** each affected represented field or group shows an icon-and-text error with an invalid visual treatment
- **AND** persistent field guidance remains visible
- **AND** no create request is sent and the draft is retained

#### Scenario: Reject an invalid nested Apply attempt
- **WHEN** a user activates `Apply changes` in a Metric Lens, Alert Lens, or Relationship editor and local validation fails
- **THEN** the editor focuses one validation summary and highlights the affected controls or groups
- **AND** no draft mutation or HTTP write occurs

#### Scenario: Inspect draft readiness before submission
- **WHEN** the Review section evaluates an incomplete draft before the user attempts Create
- **THEN** it presents neutral or incomplete readiness guidance
- **AND** does not mark fields or configuration navigation items with submitted blocking-error state

#### Scenario: Correct a value after failed validation
- **GIVEN** an explicit Create or Apply attempt displayed blocking issues
- **WHEN** the user edits an affected value without attempting validation again
- **THEN** the existing blocking feedback remains visible
- **AND** the Review and Definition Summary do not present a conflicting ready or success state
- **AND** when current draft values appear complete, the Review indicates that validation must be attempted again
- **AND** the next explicit validation replaces it with the current result

#### Scenario: Associate a field-specific API error
- **WHEN** the create API rejects the aggregate with a field path that maps to a represented field or nested child
- **THEN** the UI includes the problem in the validation summary
- **AND** associates it with the affected field or a correction link to the affected nested editor
- **AND** retains the draft for correction

### Requirement: Expose section-level issue status in Create Observation
The Create Observation configuration navigation SHALL show the number of currently displayed blocking validation issues associated with General, Metric lenses, Alert lenses, Relationships, and Review. Issue status SHALL remain visually and semantically distinct from the active-section state, and navigation items with issues SHALL continue to navigate to their corresponding sections.

#### Scenario: Show issues in multiple sections
- **WHEN** aggregate validation produces issues belonging to more than one configuration section
- **THEN** each affected navigation item shows its own blocking issue count
- **AND** the active item remains independently identifiable

#### Scenario: Navigate to a section with issues
- **WHEN** a user activates a configuration item that shows blocking issues
- **THEN** the page navigates to that existing section anchor
- **AND** retains the issue indication until the displayed validation state is updated by subsequent validation

### Requirement: Distinguish incomplete, warning, error, information, and success feedback
The system SHALL use consistent icon-and-text treatments for informational notices, non-blocking warnings or limitations, blocking errors, and successful or ready states. Color SHALL supplement rather than replace the icon and text. The system SHALL NOT present the same underlying validation condition simultaneously as separate incomplete and error messages in the Definition Summary.

#### Scenario: Show an incomplete aggregate before submission
- **GIVEN** no Lens is configured and the user has not attempted invalid aggregate submission
- **WHEN** Create Observation is displayed
- **THEN** the Definition Summary shows one amber incomplete-configuration message
- **AND** does not show a duplicate red validation message for that condition

#### Scenario: Show a blocking aggregate state after submission
- **WHEN** an invalid Create Observation attempt includes an aggregate-level Lens requirement error
- **THEN** the Definition Summary shows one red blocking state with the issue count or corrective direction
- **AND** does not repeat the raw aggregate message below it

#### Scenario: Show a transport failure
- **WHEN** a list, detail, capability, or create request fails
- **THEN** the UI presents a prominent icon-and-text error notice with the available retry or correction action
- **AND** does not present the failure as informational, empty, or analytically significant

#### Scenario: Preserve a not-found absence state
- **WHEN** read-only Observation inspection returns not found
- **THEN** the UI retains its distinct not-found presentation and return action
- **AND** does not misclassify the absence as a retryable transport failure or successful empty definition

#### Scenario: Show an operational limitation
- **WHEN** Metric configuration is unavailable because no Metric source is configured
- **THEN** the UI presents the limitation as a warning with its scope and available Alert-only path
- **AND** does not present it as a successful or purely informational state

### Requirement: Keep Relationship editor actions available in long forms
The Relationship editor SHALL group `Cancel`, `Apply changes`, and the existing rule-semantics guidance in one action-and-guidance rail. At viewports that present the editor as a two-column layout, the rail SHALL remain visible within the viewport while the user scrolls the longer form column. At narrower viewports, the actions and guidance SHALL remain in normal document flow and SHALL NOT obscure or horizontally compress the form.

The location and presentation of these controls SHALL NOT change their behavior: `Cancel` SHALL leave the aggregate draft unchanged, and `Apply changes` SHALL retain the existing validation, draft update, return navigation, and no-HTTP-write semantics.

#### Scenario: Scroll a long Relationship form on a wide viewport
- **GIVEN** the Relationship editor is using its two-column layout and the form is taller than the viewport
- **WHEN** the user scrolls through the form
- **THEN** the action-and-guidance rail containing `Cancel`, `Apply changes`, and rule semantics remains visible within the viewport
- **AND** it does not cover the editable form column

#### Scenario: Use the Relationship editor on a narrow viewport
- **WHEN** the Relationship editor cannot present its two-column layout without compressing the form
- **THEN** the action-and-guidance rail participates in normal document flow
- **AND** the actions and guidance remain readable and operable without covering form controls

#### Scenario: Preserve nested-editor action semantics
- **WHEN** the user activates `Cancel` or `Apply changes` from the action-and-guidance rail
- **THEN** the selected action has the same draft, validation, navigation, and network behavior defined for the existing nested editor

### Requirement: Present compact accessible descriptor-row actions
Each When-condition and Expect-expectation row SHALL expose removal as a compact icon-only button with an accessible name that identifies the affected section. The button SHALL retain visible keyboard focus and the same row-removal behavior as the current text action.

The `Add condition` and `Add expectation` actions SHALL be visually presented as compact secondary buttons rather than link-like text. They SHALL retain their distinct accessible names and existing row-addition behavior.

#### Scenario: Remove a descriptor row with an icon action
- **GIVEN** a When-condition or Expect-expectation row exists
- **WHEN** the user focuses or inspects its removal control
- **THEN** the control is presented as a compact icon-only button
- **AND** its accessible name identifies removal of a row from the corresponding When or Expect section
- **AND** activating it removes only that row

#### Scenario: Add a condition or expectation from a button
- **WHEN** the Relationship editor shows `Add condition` or `Add expectation`
- **THEN** each action is visually recognizable as a button and exposed as a button to assistive technology
- **AND** activating it appends one row to the corresponding section using the existing defaults
