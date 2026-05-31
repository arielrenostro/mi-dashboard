## MODIFIED Requirements

### Requirement: Connection follows a handshake sequence before streaming
The system SHALL follow this sequence on connect:
1. `EcuTransport.open()`
2. `EcuProtocol` sends `#D50` (ECU_INFO); retries every 3 attempts until response starting with `#D50` is received
3. Publishes `EcuHandshakeCompletedEvent` on the event bus
4. Enters read loop — does NOT send `#D01` here; streaming is started by `VehicleState` setup thread

#### Scenario: Handshake completes and enters read loop without streaming
- **WHEN** the ECU responds to `#D50` with a line starting with `#D50`
- **THEN** `EcuProtocol` SHALL publish `EcuHandshakeCompletedEvent` and enter the read loop without sending `#D01`

#### Scenario: Streaming starts after VehicleState setup thread calls start_streaming
- **WHEN** VehicleState setup thread calls `protocol.start_streaming()`
- **THEN** `EcuProtocol` SHALL send `#D01\n`, wait for the streaming ack response, and return `StreamingAckResponse`

## REMOVED Requirements

### Requirement: Connection follows a handshake sequence before streaming (original)
**Reason**: The original sequence included fetching breakpoints, VE map, and starting streaming as part of the connection handshake. These are now owned by `VehicleState` setup thread.
**Migration**: `EcuProtocol` handshake ends at `#D50`. `VehicleState` calls `fetch_map_breakpoints`, `fetch_rpm_breakpoints`, `fetch_ve_row(1..15)`, and `start_streaming` in sequence via named protocol methods.

### Requirement: Commands are enqueued and drained after each complete frame
**Reason**: The internal command queue and drain-after-frame pattern are replaced by `_send_and_wait` with `_write_lock`. Commands are sent immediately when the caller acquires the lock. No drain queue exists.
**Migration**: All command senders call `EcuProtocol` named methods (via `VehicleState`). `_write_lock` serializes concurrent callers.

## ADDED Requirements

### Requirement: EcuProtocol read loop routes lines by prefix
The read loop in `EcuProtocol` SHALL classify each line received from `EcuTransport.read_line()`:
- Lines starting with `#D01`, `#D02`, or `#D03`: publish `EcuFrameReceivedEvent` immediately
- Lines matching the active `_pending` prefix: deliver to the blocked `send_and_wait` caller via `threading.Event`
- Other lines: log and discard

#### Scenario: D01 and D02 are routed to frame events independently
- **WHEN** the read loop receives `#D01;...`
- **THEN** SHALL publish `EcuFrameReceivedEvent(D01, values)` without waiting for `#D02`

#### Scenario: Command response is routed to the pending caller
- **WHEN** the read loop receives a line starting with the active `_pending` prefix (e.g., `#F01`)
- **THEN** SHALL deliver the line to `_send_and_wait` caller and set `_pending = None`

### Requirement: _write_lock serializes concurrent send_and_wait callers
`EcuProtocol` SHALL maintain a single `_write_lock: threading.Lock`. Any caller of `_send_and_wait` MUST acquire this lock before writing. The lock is released immediately after writing — it does NOT block while waiting for the response.

#### Scenario: Two concurrent callers are serialized
- **WHEN** VehicleState setup thread and VeWriteController call protocol methods concurrently
- **THEN** the second caller SHALL block on `_write_lock` until the first caller's `send_and_wait` completes and the lock is released

#### Scenario: Write and read loop are parallel
- **WHEN** a caller holds `_write_lock` and writes to the transport
- **THEN** the ECU thread read loop SHALL continue calling `transport.read_line()` without interruption
