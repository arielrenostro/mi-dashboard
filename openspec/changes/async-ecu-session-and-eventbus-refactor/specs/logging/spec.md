## MODIFIED Requirements

### Requirement: LogWriter subscribes to ECU_MESS_FRAME and accumulates before writing
`LogWriter` MUST subscribe to `ECU_MESS_FRAME` on the event bus. It SHALL accumulate the `#D01` and `#D02` frames internally. When both `#D01` and `#D02` have been received for the current cycle, it SHALL write one CSV row combining their data. If only `#D01` arrives and no `#D02` follows within 500 ms, the row SHALL be written with the `#D01` data only and a `"PARTIAL"` flag in the Event column.

#### Scenario: Full row is written after D01 and D02 arrive
- **WHEN** `ECU_MESS_FRAME` events for `#D01` and `#D02` arrive within 500 ms of each other
- **THEN** `LogWriter` SHALL write one CSV row combining fields from both frames

#### Scenario: Partial row is written after timeout
- **WHEN** `ECU_MESS_FRAME` for `#D01` arrives but `#D02` does not arrive within 500 ms
- **THEN** `LogWriter` SHALL write a row with D01 data and `"PARTIAL"` in the Event column

#### Scenario: D03 frames are not logged
- **WHEN** `ECU_MESS_FRAME` with `frame_type="D03"` arrives
- **THEN** `LogWriter` SHALL ignore the frame (no CSV row written for D03-only data)

### Requirement: Each row contains timestamp, event flag, and raw ECU fields from D01+D02
Each data row MUST contain the following columns in order:
- Col 0 `Timestamp`: Unix timestamp in milliseconds (`int(time.time() * 1000)`)
- Col 1 `Event`: `"MARK"` if an event was pending, `"PARTIAL"` if D02 was missing, otherwise empty
- Cols 2+: raw tokens from `#D01;...` followed by raw tokens from `#D02;...`, each split on `;` with the `#D01`/`#D02` prefix stripped

#### Scenario: Timestamp is in milliseconds
- **WHEN** a row is written
- **THEN** the Timestamp column SHALL contain `int(time.time() * 1000)`

#### Scenario: Raw values are stored without conversion
- **WHEN** a frame with a raw CLT value of `363` (Kelvin) is logged
- **THEN** the log SHALL contain `363`, not `90` (Celsius)

### Requirement: Log file is a semicolon-delimited CSV
The system SHALL write a semicolon-delimited CSV log file with UTF-8 encoding, LF line terminators, opened in append mode. The header row MUST be written once when the file does not yet exist. Every row MUST be flushed to disk immediately after writing.

#### Scenario: Header is written on first run
- **WHEN** the log file does not exist and the first row is ready to write
- **THEN** the header row SHALL be written before the first data row

#### Scenario: Append mode preserves existing data on restart
- **WHEN** the application restarts and the log file already exists
- **THEN** new rows SHALL be appended without overwriting existing content

### Requirement: Event marking attaches to the next complete row
When `EventMarkRequestedEvent` is received via the bus, `LogWriter` MUST set an internal flag. The next complete (or partial) row written SHALL contain `"MARK"` in the Event column and the flag SHALL be cleared. `"MARK"` takes precedence over `"PARTIAL"` (both MUST NOT appear in the same cell; `"MARK"` wins).

#### Scenario: Mark appears on the next complete row
- **WHEN** Enter is pressed and then a D01+D02 pair completes
- **THEN** that row SHALL have `"MARK"` in the Event column

#### Scenario: Mark takes precedence over PARTIAL
- **WHEN** Enter is pressed and the next row is PARTIAL (D02 timeout)
- **THEN** the Event column SHALL contain `"MARK"`, not `"PARTIAL"`

### Requirement: Log writes happen on a dedicated thread
`LogWriter` MUST own a `Worker` object moved to a dedicated `QThread`. All disk writes MUST happen on that worker thread via a queued `pyqtSignal(list)`. Accumulation of frames (D01+D02 pairing) MUST happen on the worker thread, not the main thread.

#### Scenario: Write call is non-blocking on the calling thread
- **WHEN** `ECU_MESS_FRAME` arrives and `LogWriter` processes it
- **THEN** disk I/O SHALL happen on the worker thread without blocking the bus dispatch

## REMOVED Requirements

### Requirement: Each row contains raw tokens from joined D01+D02 string
**Reason**: `LogWriter` no longer receives a pre-joined string. It receives individual `ECU_MESS_FRAME` events and accumulates them.
**Migration**: Column layout is preserved (D01 fields followed by D02 fields), but the source is now two separate frames accumulated before writing.
