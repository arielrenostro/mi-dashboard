## MODIFIED Requirements

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
