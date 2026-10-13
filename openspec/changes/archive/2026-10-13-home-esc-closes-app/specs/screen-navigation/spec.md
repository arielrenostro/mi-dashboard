## ADDED Requirements

### Requirement: Exit with ESC on Home
On the Home screen, pressing ESC SHALL close the window and exit the app. Auto-repeat events SHALL be ignored.

#### Scenario: Exit from Home
- **WHEN** the user presses ESC on the Home screen
- **THEN** the app closes

#### Scenario: Held ESC after returning to Home
- **WHEN** the user holds ESC on the Dashboard until it returns to Home
- **THEN** the app does not exit until ESC is released and pressed again
