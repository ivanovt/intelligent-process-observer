## ADDED Requirements

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
