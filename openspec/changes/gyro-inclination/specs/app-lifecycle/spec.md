## ADDED Requirements

### Requirement: Inclinometer connection stops on shutdown
When the app shuts down, the inclinometer connection SHALL be stopped together with the ECU source, after the window is closed and before the datalog is closed: its serial port SHALL be closed and its thread SHALL have finished before the process exits. Waiting for it SHALL be bounded to 1 second; when it does not finish in time the app SHALL log a warning and continue. A failure while stopping it SHALL be logged and SHALL NOT prevent the remaining components from being stopped. When the inclinometer is not configured nothing SHALL be stopped and nothing SHALL fail.

#### Scenario: Port closed
- **WHEN** the inclinometer port is open and the user closes the app
- **THEN** the port is closed and the process ends with exit status 0

#### Scenario: Not configured
- **WHEN** `gyro.port` is empty and the user closes the app
- **THEN** shutdown completes normally

#### Scenario: Stop fails
- **WHEN** stopping the inclinometer connection raises an error
- **THEN** the error is logged and the ECU source, the alarm and the datalog are still stopped
