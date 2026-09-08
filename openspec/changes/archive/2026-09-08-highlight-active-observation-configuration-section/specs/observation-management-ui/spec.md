## ADDED Requirements

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
