## ADDED Requirements

### Requirement: Connection error overlay
When a connection error is reported, the app SHALL show a square, dialog-like overlay centered over the current screen, containing a title and the error message, and SHALL close it automatically 2 seconds after it was shown. At most one overlay SHALL be visible; a new report while it is visible SHALL replace its message and restart the 2 seconds. The overlay SHALL be visible on every screen, SHALL NOT be dismissed by or consume keyboard input, and SHALL NOT change which screen is active.

#### Scenario: Error shown and closed
- **WHEN** a connection error is reported
- **THEN** the overlay appears with the message and disappears 2 seconds later

#### Scenario: Keys keep working
- **WHEN** the overlay is visible and the user presses a key
- **THEN** the key is handled by the current screen as usual and the overlay stays until its timeout

#### Scenario: New error while visible
- **WHEN** a different error is reported 1 second after the overlay appeared
- **THEN** the overlay shows the new message and closes 2 seconds after that report
