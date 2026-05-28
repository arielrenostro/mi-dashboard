## ADDED Requirements

### Requirement: EcuSession manages its own internal I/O thread
`EcuSession` SHALL internally create and manage a single I/O thread. Callers SHALL NOT need to instantiate or start a separate thread. `start()` SHALL begin the thread; `stop()` SHALL signal it to exit and join it. The thread SHALL NOT be accessible outside the session.

#### Scenario: Thread starts on session start
- **WHEN** `session.start()` is called
- **THEN** the internal I/O thread SHALL be running and processing data

#### Scenario: Thread stops cleanly on session stop
- **WHEN** `session.stop()` is called
- **THEN** the I/O thread SHALL exit within 2 s and all resources SHALL be released

### Requirement: EcuSession performs handshake on connection
On `start()`, `EcuSession` SHALL execute the handshake sequence:
1. Open transport
2. Send `#D50` (ECU_INFO); retry every attempt until response starting with `#D50` is received (max 10 attempts, 1 s apart)
3. Send `#D01` (STREAMING_START); retry until response starting with `#D01`, `#D02`, or `#D03`
4. Enter read loop

#### Scenario: Handshake completes and enters read loop
- **WHEN** the ECU responds to `#D50` with a `#D50` line
- **THEN** the session SHALL proceed to send `#D01` and enter the read loop

#### Scenario: Handshake retries on no response
- **WHEN** no response is received within 1 s of sending `#D50`
- **THEN** the session SHALL retry sending `#D50` up to 10 times before reporting failure

### Requirement: EcuSession reads and writes concurrently without blocking
The I/O thread SHALL perform reads with a short timeout (50 ms). Between reads, it SHALL drain the write queue and send any pending commands. Write operations SHALL never block the read loop for more than one write round-trip.

#### Scenario: Command is sent between reads
- **WHEN** a command is enqueued while the I/O thread is in a read timeout
- **THEN** the command SHALL be sent before the next read completes

#### Scenario: Streaming continues while commands are sent
- **WHEN** a `send_command()` call is in progress
- **THEN** incoming `#D01`/`#D02`/`#D03` frames SHALL continue to be published on the bus without interruption

### Requirement: EcuSession publishes ECU_MESS_FRAME for each incoming frame
When the I/O thread reads a line starting with `#D01`, `#D02`, or `#D03`, it SHALL immediately publish an `EcuMessFrameEvent` on the bus for that individual frame. Publication SHALL happen via `QueuedConnection` to the main thread.

#### Scenario: D01 frame is published independently
- **WHEN** a `#D01;...` line is received
- **THEN** `ECU_MESS_FRAME` SHALL be published with `frame_type="D01"` and `line` as the raw string

#### Scenario: D02 frame is published independently
- **WHEN** a `#D02;...` line is received
- **THEN** `ECU_MESS_FRAME` SHALL be published with `frame_type="D02"` and the raw line

### Requirement: EcuSession pairs commands with responses
`send_command(cmd, args)` SHALL enqueue the command, then block on a `threading.Event` with a 5 s timeout. The I/O thread SHALL match the first incoming line whose prefix equals the command code to resolve the Event. `send_command` SHALL return the raw response line, or raise `EcuTimeoutError` on timeout.

#### Scenario: Command is resolved by matching response
- **WHEN** `#F01;...` is sent and the ECU replies with `#F01;...`
- **THEN** `send_command` SHALL return the response line and unblock the caller

#### Scenario: Timeout raises EcuTimeoutError
- **WHEN** no matching response arrives within 5 s
- **THEN** `send_command` SHALL raise `EcuTimeoutError`

#### Scenario: ECU_COMMAND_SEND is published on send
- **WHEN** a command string is written to the transport
- **THEN** `ECU_COMMAND_SEND` SHALL be published on the bus with the command code and args

#### Scenario: ECU_COMMAND_RESPONSE is published on response
- **WHEN** a response line is matched to a pending command
- **THEN** `ECU_COMMAND_RESPONSE` SHALL be published on the bus with the response line

### Requirement: EcuSession reconnects after three consecutive empty reads
In the read loop, if three consecutive reads return empty strings, the session SHALL close the transport and restart the handshake sequence without stopping the I/O thread.

#### Scenario: Reconnect triggers on three consecutive empty reads
- **WHEN** three consecutive `read_line()` calls return empty strings
- **THEN** the session SHALL close the transport and restart the handshake

### Requirement: EcuSession is accessible via module-level registry
A module-level `get_ecu_session()` / `register_ecu_session()` API SHALL allow any module to access the active session without holding a direct reference. This mirrors the existing `get_ecu_connection()` pattern.

#### Scenario: Session is accessible after registration
- **WHEN** `register_ecu_session(session)` is called during startup
- **THEN** `get_ecu_session()` SHALL return the same instance from any module
