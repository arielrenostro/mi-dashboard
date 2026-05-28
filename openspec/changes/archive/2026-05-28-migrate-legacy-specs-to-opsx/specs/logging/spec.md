## ADDED Requirements

### Requirement: Log file is a semicolon-delimited CSV
The system SHALL write a semicolon-delimited CSV log file with UTF-8 encoding (system default), LF line terminators, opened in append mode. The header row MUST be written once when the file does not yet exist. Every row MUST be flushed to disk immediately after writing.

#### Scenario: Header is written on first run
- **WHEN** the log file does not exist and the first frame arrives
- **THEN** the header row SHALL be written before the first data row

#### Scenario: Append mode preserves existing data on restart
- **WHEN** the application restarts and the log file already exists
- **THEN** new rows SHALL be appended without overwriting existing content

### Requirement: Each row contains timestamp, event flag, and all raw ECU fields
Each data row MUST contain the following columns in order:
- Col 0 `Timestamp`: Unix timestamp in milliseconds (`int(time.time() * 1000)`)
- Col 1 `Event`: `"MARK"` if an event was pending, otherwise empty
- Cols 2+: raw tokens from the joined `#D01;...;#D02;...` frame split on `;`

Raw values are logged without conversion. Display-time conversion (from signals spec) is applied by `SignalProcessor` and is NOT stored in the log.

#### Scenario: Timestamp is in milliseconds
- **WHEN** a row is written
- **THEN** the Timestamp column SHALL contain `int(time.time() * 1000)`

#### Scenario: Raw values are stored without conversion
- **WHEN** a frame with a raw CLT value of `363` (Kelvin) is logged
- **THEN** the log SHALL contain `363`, not `90` (Celsius)

### Requirement: Event marking attaches to the next arriving frame
When the user presses Enter/Return, `EventMarker` publishes `EventMarkRequestedEvent`. `LogWriter.set_event_pending()` MUST set an internal flag. The next call to `LogWriter.write()` MUST write `"MARK"` in the Event column and clear the flag. The mark is attached to the **next** frame, not a synthetic row.

#### Scenario: Mark appears on the next real frame
- **WHEN** Enter is pressed and then a new frame arrives
- **THEN** that frame's row SHALL have `"MARK"` in the Event column

#### Scenario: Only one row is marked per key press
- **WHEN** Enter is pressed once
- **THEN** exactly one subsequent row SHALL contain `"MARK"`

### Requirement: Log writes happen on a dedicated thread
`LogWriter` MUST own a `Worker` object moved to a dedicated `QThread`. All disk writes MUST happen on that worker thread via a queued `pyqtSignal(list)`. The main thread and ECU thread MUST call `LogWriter.write()` which enqueues the write — they MUST NOT write to disk directly.

#### Scenario: Write call is non-blocking on the calling thread
- **WHEN** `LogWriter.write()` is called from the ECU reader thread
- **THEN** the call SHALL return immediately without blocking on disk I/O
