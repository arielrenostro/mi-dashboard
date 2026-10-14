## MODIFIED Requirements

### Requirement: Connect and synchronize sequence
On connect, the serial source SHALL perform in order: open the port; send the ECU info command until an `#D50` response arrives; request MAP breakpoints and then RPM breakpoints and publish both axes to the shared state only when both responses are non-empty; request all 16 VE map rows (`#F01` to `#F16`) and publish each response to the shared state; request all 16 ignition map rows (`#I01` to `#I16`) and publish each response to the shared state; send the streaming start command until a telemetry response (`#D01`, `#D02` or `#D03`) arrives. A command awaiting a response SHALL be re-sent after every 3 reads without a matching response, indefinitely while the connection is running.

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

#### Scenario: Ignition rows loaded before streaming
- **WHEN** the ECU answers every ignition row request
- **THEN** all 16 rows of the shared ignition map hold the received values before the streaming start command is sent

## ADDED Requirements

### Requirement: Ignition row publication
Each ignition row response SHALL be stored in the shared state at the row index matching its number and announced as a change event.

#### Scenario: Row response
- **WHEN** `#I03;...` with 16 values is received during synchronization
- **THEN** row index 2 of the shared ignition map is replaced and a change event is emitted

### Requirement: Mock ignition map
The mock source SHALL, when started, also publish a fixed ignition map (16 rows of 16 values, with the lowest-MAP row at index 0) to the shared state, so the ignition tuning screen can be exercised without hardware.

#### Scenario: Mock start
- **WHEN** the mock source starts
- **THEN** all 16 rows of the shared ignition map are published
