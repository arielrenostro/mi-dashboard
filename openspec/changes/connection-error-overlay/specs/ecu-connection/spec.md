## ADDED Requirements

### Requirement: Connection error reporting
The serial source SHALL report a human-readable connection error message, including the underlying error detail when one exists, when: opening the port fails; a read or write error forces a reconnect; or three consecutive empty reads force a reconnect. A message identical to the last reported one SHALL NOT be reported again until a different message is reported or the connection reaches CONNECTED. Reports SHALL be delivered to the UI thread. The mock source SHALL NOT report errors.

#### Scenario: Port missing
- **WHEN** opening the configured port fails
- **THEN** one error message with the failure detail is reported

#### Scenario: Same error repeats
- **WHEN** every retry fails with the same error
- **THEN** the message is reported only once

#### Scenario: Different error
- **WHEN** a retry fails with a different error
- **THEN** the new message is reported

#### Scenario: Recovery re-arms reporting
- **WHEN** the connection reaches CONNECTED and later fails with the earlier error
- **THEN** the message is reported again

### Requirement: Connect retry pacing
After a failed connection attempt the serial source SHALL wait 1 second before the next attempt, and SHALL stop waiting promptly when the app is stopping.

#### Scenario: Port unavailable
- **WHEN** the port cannot be opened
- **THEN** attempts are made about once per second instead of continuously
