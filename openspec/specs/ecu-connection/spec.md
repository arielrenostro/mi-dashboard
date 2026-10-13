# ecu-connection Specification

## Purpose

Describes how the app connects to the ECU (real serial link or mock replay), synchronizes ECU data, assembles telemetry frames, recovers from failures, exposes connection status and accepts commands from any part of the app.

## Requirements

### Requirement: Source selection
The system SHALL use the mock source when `connection.mock` is non-empty and the serial source otherwise. The chosen source SHALL run on its own background thread and deliver each received line to the rest of the app.

#### Scenario: Serial source
- **WHEN** `connection.mock` is empty
- **THEN** the app opens the configured serial port and baud rate

#### Scenario: Mock source
- **WHEN** `connection.mock` is a path
- **THEN** no serial port is opened

### Requirement: Connect and synchronize sequence
On connect, the serial source SHALL perform in order: open the port; send the ECU info command until an `#D50` response arrives; request MAP breakpoints and then RPM breakpoints and publish both axes to the shared state only when both responses are non-empty; request all 16 VE map rows (`#F01` to `#F16`) and publish each response to the shared state; send the streaming start command until a telemetry response (`#D01`, `#D02` or `#D03`) arrives. A command awaiting a response SHALL be re-sent after every 3 reads without a matching response, indefinitely while the connection is running.

#### Scenario: Normal connect
- **WHEN** the ECU answers every request
- **THEN** status moves CONNECTING, HANDSHAKE, CONNECTED and telemetry starts flowing

#### Scenario: Silent ECU
- **WHEN** the ECU does not answer a request
- **THEN** the request is re-sent every third read and the sequence does not advance

#### Scenario: Port cannot be opened
- **WHEN** opening the port fails
- **THEN** the failure is logged and the attempt is repeated until it succeeds or the app stops

#### Scenario: Highest-MAP row loaded
- **WHEN** the ECU answers the `#F16` request
- **THEN** row index 15 of the shared VE map holds the received values

### Requirement: VE row publication
Each VE row response SHALL be stored in the shared state at the row index matching its number and announced as a change event.

#### Scenario: Row response
- **WHEN** `#F03;...` with 16 values is received during synchronization
- **THEN** row index 2 of the shared VE map is replaced and a change event is emitted

### Requirement: Frame assembly
While streaming, the serial source SHALL keep the latest `#D01` line and latest `#D02` line. When both are present it SHALL emit exactly one combined `#D01...;#D02...` line and clear both buffers. Any other non-empty line SHALL be emitted unchanged.

#### Scenario: Complete cycle
- **WHEN** a `#D01` line and a `#D02` line have arrived
- **THEN** one combined line is emitted and the buffers are cleared

#### Scenario: Incomplete cycle
- **WHEN** only a `#D01` line has arrived
- **THEN** nothing combined is emitted yet

### Requirement: Failure recovery
The serial source SHALL close the port and run the full connect and synchronize sequence again after 3 consecutive empty reads, or after any read or write error. Reconnecting SHALL reload breakpoints and VE rows from the ECU.

#### Scenario: Silent link
- **WHEN** three consecutive reads return no data
- **THEN** the port is closed and the connect sequence restarts

#### Scenario: I/O error
- **WHEN** reading raises an error
- **THEN** the port is closed and the connect sequence restarts

### Requirement: Command queue
Any part of the app SHALL be able to request a command, optionally with arguments, from any thread. Commands SHALL be written in first-in first-out order, and only between reads: after a complete telemetry cycle or after a non-telemetry line.

#### Scenario: Command during streaming
- **WHEN** a command is requested while telemetry is streaming
- **THEN** it is written after the next complete telemetry cycle

#### Scenario: Order
- **WHEN** two commands are requested in sequence
- **THEN** they are written in that order

### Requirement: Connection status
The connection SHALL report one of CONNECTED, DISCONNECTED, CONNECTING, HANDSHAKE or ERROR. Closing the port sets DISCONNECTED. For the mock source, the status SHALL be CONNECTED while the source is running and DISCONNECTED otherwise.

#### Scenario: Link lost
- **WHEN** the port is closed after a failure
- **THEN** the status is DISCONNECTED until the next connect attempt starts

### Requirement: Mock replay
The mock source SHALL, when started, publish a fixed set of breakpoints and a fixed VE map to the shared state. It SHALL skip the first line of the file (the header), then, on its first pass only, skip the number of data lines given by `connection.mock_skip_lines` (default `0`), then emit every following line (trimmed) at one line every 0.1 seconds, and restart from the first data line when it ends without skipping again. Lines that do not start with `#D01` are ignored by downstream consumers. Commands sent to the mock SHALL have no effect on the replay.

#### Scenario: Replay pace
- **WHEN** the mock is running
- **THEN** one line is emitted every 0.1 seconds

#### Scenario: End of file
- **WHEN** the last line has been emitted
- **THEN** the replay restarts from the second line of the file

#### Scenario: Configured skip
- **WHEN** `connection.mock_skip_lines` is `500`
- **THEN** the first emitted line is the 501st data line

#### Scenario: Restart after skip
- **WHEN** the end of the file is reached after a first pass that skipped lines
- **THEN** the replay restarts from the first data line

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
