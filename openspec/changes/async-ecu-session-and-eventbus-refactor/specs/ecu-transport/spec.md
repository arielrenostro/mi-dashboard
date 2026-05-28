## ADDED Requirements

### Requirement: EcuTransport abstracts raw serial I/O
`EcuTransport` SHALL be an abstract base class exposing `read_line() -> str` and `write_line(line: str) -> None`. It SHALL have no knowledge of protocol framing, command pairing, or events. Implementations: `SerialTransport` (real port) and `MockTransport` (CSV replay).

#### Scenario: Read returns a single line
- **WHEN** `read_line()` is called and a line is available on the port
- **THEN** it SHALL return the line without the line terminator

#### Scenario: Read returns empty string on timeout
- **WHEN** no data arrives within the read timeout (1 s)
- **THEN** `read_line()` SHALL return an empty string without raising an exception

#### Scenario: Write sends line with LF terminator
- **WHEN** `write_line("cmd")` is called
- **THEN** the transport SHALL send `"cmd\n"` encoded as UTF-8 to the serial port

### Requirement: SerialTransport connects to a configurable COM port
`SerialTransport` SHALL open a serial port with parameters from `config.json` (`port`, `baudrate`). Read timeout SHALL be 1 s. Write timeout SHALL be 1 s. Encoding SHALL be UTF-8 with LF line terminator.

#### Scenario: Port is opened with configured parameters
- **WHEN** `SerialTransport` is instantiated with `port="COM5"` and `baudrate=115200`
- **THEN** the serial port SHALL open on COM5 at 115200 baud

#### Scenario: Transport can be closed and reopened
- **WHEN** `close()` is called followed by a new `open()` call
- **THEN** the port SHALL reconnect without error

### Requirement: MockTransport replays a CSV log file
`MockTransport` SHALL replay rows from a recorded CSV log file. It SHALL emit lines paced by the `Timestamp` column delta when available, falling back to immediate emission. `write_line()` SHALL be a no-op. The emitted lines SHALL be individual `#D01`/`#D02` lines (not joined), one per `read_line()` call.

#### Scenario: Mock emits D01 and D02 as separate reads
- **WHEN** a CSV row contains both `#D01` and `#D02` data
- **THEN** `read_line()` SHALL first return the `#D01` line, then the `#D02` line on the next call

#### Scenario: Mock write is ignored
- **WHEN** `write_line("cmd")` is called on MockTransport
- **THEN** no action SHALL be taken and no exception SHALL be raised
