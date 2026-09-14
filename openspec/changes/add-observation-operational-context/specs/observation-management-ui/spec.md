## ADDED Requirements

### Requirement: Edit optional operational context without expanding the configuration flow

The Create and Edit Observation flows SHALL keep `operational_context` in the General section immediately after Objective. One accessible disclosure labelled `Add operational context (optional)` SHALL be collapsed initially for an empty value and expanded when an existing non-empty value is loaded for editing. A populated disclosure that the operator collapses SHALL show a short text preview without truncating or changing the draft value. It SHALL reveal a multiline text field with concise guidance that the text describes operating conditions, expected behavior, or terminology and is sent to the Reasoning and Report agents during a run. It SHALL not add a configuration navigation item, nested editor, model call during editing, or separate save action.

The field SHALL remain in the single client-side Observation aggregate draft. Empty input SHALL serialize as `null`; non-empty text SHALL be submitted with the final create or replacement request without trimming or rewriting. The UI SHALL validate the same non-whitespace and 4,000-code-point limits as the backend, associate errors with the field, and expand the disclosure when an error must be shown. Review and read-only definition inspection SHALL display the complete stored value with line breaks preserved, or a clear absent state. Existing definition-list search SHALL remain limited to name and description.

#### Scenario: Leave optional context empty
- **GIVEN** the operator opens a new Observation draft
- **WHEN** the General section appears
- **THEN** the optional disclosure is collapsed and the rest of the form remains available
- **AND** final creation submits `operational_context: null` if the operator leaves it empty

#### Scenario: Add context through the existing aggregate draft
- **GIVEN** the operator expands the disclosure and enters multiple lines of valid context
- **WHEN** they review and submit the Observation
- **THEN** Review shows the complete text and the final aggregate request contains it exactly
- **AND** no request is sent merely because the field was edited

#### Scenario: Edit a populated definition
- **GIVEN** the operator opens Edit for a definition with stored operational context
- **WHEN** the draft is initialized
- **THEN** the disclosure is expanded with the exact stored value
- **AND** collapsing it shows a short preview while preserving the full draft value

#### Scenario: Show context validation at its control
- **GIVEN** the operator enters blank-only or oversized context
- **WHEN** they attempt to create or save the aggregate
- **THEN** the disclosure opens and the field shows its associated error
- **AND** the draft is retained for correction without a successful write

#### Scenario: Inspect saved context without changing search
- **GIVEN** a stored Observation has operational context
- **WHEN** the operator opens its read-only definition
- **THEN** the full text is presented as configuration data with line breaks preserved
- **AND** the definitions list does not search or display the full text
