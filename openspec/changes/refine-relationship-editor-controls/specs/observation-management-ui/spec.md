## ADDED Requirements

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
