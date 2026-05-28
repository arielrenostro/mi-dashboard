## ADDED Requirements

### Requirement: Serial transport parameters are fixed
The system SHALL connect via Bluetooth serial (Windows COM port) with these defaults: port `COM1` (configurable via `config.json`), baud rate 115200, read/write timeout 1 s, encoding UTF-8, line terminator `\n`.

#### Scenario: Connection uses configured port
- **WHEN** `config.json` specifies `connection.port = "COM5"`
- **THEN** the serial connection SHALL open on `COM5`

### Requirement: Frame format is a semicolon-delimited joined string
The ECU streams two frame types per cycle: `#D01;<v1>;<v2>;...` and `#D02;<v1>;<v2>;...`. The connection layer MUST wait for exactly one `#D01` and one `#D02` per cycle, join them as `#D01;...;#D02;...`, and emit the combined string. Signal indices in the signals spec refer to absolute positions in this joined string.

#### Scenario: Joined frame is emitted after both halves arrive
- **WHEN** a `#D01` line and a `#D02` line have both been buffered
- **THEN** the system SHALL emit `"{d01};{d02}"` and clear both buffers

### Requirement: Connection follows a handshake sequence before streaming
The system SHALL follow this sequence on connect:
1. Open serial port
2. Send `#D50` (ECU_INFO); retry every 3 attempts until response starting with `#D50` is received
3. Send `#D01` (STREAMING_START); retry every 3 attempts until response starting with `#D01`, `#D02`, or `#D03`
4. Enter read loop

#### Scenario: Handshake completes successfully
- **WHEN** the ECU responds to `#D50` with a line starting with `#D50`
- **THEN** the system SHALL proceed to send `#D01` to start streaming

### Requirement: Read loop reconnects after three consecutive empty reads
In the read loop, if three consecutive `readline()` calls return empty strings, the connection MUST close and restart from step 1 of the handshake sequence.

#### Scenario: Reconnect triggers on three empty reads
- **WHEN** three consecutive readline calls return empty strings
- **THEN** the system SHALL close the port and restart the handshake sequence

### Requirement: Commands are enqueued and drained after each complete frame
`send_command(cmd)` MUST be thread-safe via an internal `queue.Queue`. Commands are drained after each complete `#D01 + #D02` pair is emitted, never mid-frame. Multiple commands in the queue are sent in FIFO order. Commands are sent as `"{cmd}\n"` in UTF-8.

#### Scenario: Command is sent after frame completion
- **WHEN** a command is enqueued and the next complete frame is emitted
- **THEN** the command SHALL be sent to the serial port before the next read cycle begins

#### Scenario: Command queue is FIFO
- **WHEN** two commands are enqueued in order A then B
- **THEN** command A SHALL be sent before command B

### Requirement: Mock mode replays a CSV log file
When configured, `EcuConnectionMock` MUST replace `EcuConnectionSerial`. It SHALL replay rows from a recorded CSV log file, pacing emissions using the `Timestamp` column when available. `send_command()` is a no-op. The emitted format MUST be identical to the real connection (`#D01;...;#D02;...`).

#### Scenario: Mock emits same format as real connection
- **WHEN** mock mode is active and a log row is replayed
- **THEN** the emitted string SHALL have the same `#D01;...;#D02;...` format as a real frame
