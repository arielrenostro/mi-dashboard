## MODIFIED Requirements

### Requirement: Frame format is individual per type, published via bus
The ECU streams frame types per cycle: `#D01;<v1>;<v2>;...`, `#D02;<v1>;<v2>;...`, and optionally `#D03;<v1>;<v2>;...`. `EcuSession` MUST publish each frame individually as `ECU_MESS_FRAME` immediately upon receipt. The joining of `#D01` and `#D02` into a combined string is REMOVED. Subscribers that need both frames MUST accumulate them independently.

#### Scenario: D01 and D02 are published as separate events
- **WHEN** a `#D01` line and a `#D02` line arrive in the same cycle
- **THEN** two separate `ECU_MESS_FRAME` events SHALL be published, one for each

#### Scenario: D03 frame is published independently
- **WHEN** a `#D03;...` line is received
- **THEN** `ECU_MESS_FRAME` SHALL be published with `frame_type="D03"` and the raw line

### Requirement: Commands are sent and matched to responses by code
Every command sent by the system SHALL be followed by exactly one response from the ECU whose first token matches the command code. `EcuSession` MUST register the expected response code before sending and resolve it when matched. Multiple simultaneous pending commands SHALL NOT be supported; commands are sent sequentially.

#### Scenario: Response with matching code resolves the pending command
- **WHEN** `#F01;row;v1;...` is sent and the ECU replies with `#F01;row;v1;...`
- **THEN** the response SHALL be matched to the pending command and returned to the caller

#### Scenario: MESS_FRAME lines do not resolve pending commands
- **WHEN** a `#D01` line arrives while a command response is pending
- **THEN** the `#D01` line SHALL be published as `ECU_MESS_FRAME` and the pending command SHALL remain unresolved

### Requirement: Connection follows a handshake sequence before streaming
The system SHALL follow this sequence on connect:
1. Open transport
2. Send `#D50` (ECU_INFO); retry every 1 s until response starting with `#D50` is received (max 10 attempts)
3. Send `#D01` (STREAMING_START); retry until response starting with `#D01`, `#D02`, or `#D03`
4. Enter read loop

#### Scenario: Handshake completes successfully
- **WHEN** the ECU responds to `#D50` with a line starting with `#D50`
- **THEN** the session SHALL proceed to send `#D01` to start streaming

### Requirement: Read loop reconnects after three consecutive empty reads
In the read loop, if three consecutive `read_line()` calls return empty strings, the session MUST close the transport and restart from step 1 of the handshake sequence without stopping the I/O thread.

#### Scenario: Reconnect triggers on three empty reads
- **WHEN** three consecutive read calls return empty strings
- **THEN** the session SHALL close the transport and restart the handshake sequence

## REMOVED Requirements

### Requirement: Frame format is a semicolon-delimited joined string
**Reason**: Replaced by individual `ECU_MESS_FRAME` events per frame type. Joining D01+D02 is no longer performed by the session layer.
**Migration**: `SignalProcessor` and `LogWriter` MUST subscribe to `ECU_MESS_FRAME` and accumulate frames as needed. Any code expecting the joined `"#D01;...;#D02;..."` format must be updated.

### Requirement: Commands are enqueued and drained after each complete frame
**Reason**: Commands are now sent concurrently with reads using a write queue drained between read timeouts. The D01+D02 completion gate is removed.
**Migration**: Command dispatch now happens in the I/O thread's write-drain step, not after a complete frame pair.
