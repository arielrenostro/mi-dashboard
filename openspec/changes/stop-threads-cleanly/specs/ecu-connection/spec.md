## MODIFIED Requirements

### Requirement: Shutdown
When the app exits, the connection SHALL stop, close the serial port and finish its thread. Stopping SHALL also end a connect loop that is still retrying (for example because the port cannot be opened) and any request that is still waiting for an ECU answer.

#### Scenario: Exit
- **WHEN** the user closes the app
- **THEN** the port is closed

#### Scenario: Exit while the port is unavailable
- **WHEN** the port cannot be opened and the user closes the app
- **THEN** the connection thread finishes within its bounded wait

#### Scenario: Exit during the handshake
- **WHEN** the ECU does not answer a request and the user closes the app
- **THEN** the wait for the answer ends and the connection thread finishes

#### Scenario: Exit during a mock replay
- **WHEN** the user closes the app while the mock source is replaying
- **THEN** the replay thread finishes
