# datalog Specification

## Purpose

Defines the CSV data log that records every raw telemetry frame received during a run, with a millisecond timestamp and an optional event mark.

## Requirements

### Requirement: One file per run
At startup the system SHALL create a log file named `log_stream_YYYYMMDD_HHMMSS.csv` (local start time) inside the configured `datalog.path`. The file SHALL be semicolon-delimited with `\n` line endings. The header row SHALL be written when the file did not exist before.

#### Scenario: Start of run
- **WHEN** the app starts at 2026-05-26 14:03:09
- **THEN** the file `log_stream_20260526_140309.csv` is created with the header row

### Requirement: Header columns
The header SHALL be, in order: `Timestamp`, `Event`, `Mess 1`, `RPM`, `MAP`, `Boost`, `Load %`, `Idle`, `Lambda 1`, `Inj. Pulse`, `Inj. Utiliz.`, `VE Value`, `Ign. Adv.`, `Knock`, `A/C Input`, `Start Input`, `Outputs 1`, `Outputs 2`, `Lambda 2`, `Mess 2`, `Batt Volt.`, `CLT`, `IAT`, `Inj. DT`, `Ign. Dwell`, `KM/H`, `Lambda Loop`, `Lambda Target`, `Lambda Corr`, `Strobo Angle`, `Turbo Target`, `ACC %`, `ACP %`, `dACC %`, `0`, `0`.

#### Scenario: Column count
- **WHEN** the header is read
- **THEN** it has 36 columns

### Requirement: One row per telemetry frame
For every received line that starts with `#D01` and has at least 2 fields, the system SHALL append one row: the Unix time in milliseconds, the Event value, then every field of the line split on `;` in original order and unconverted. Lines not starting with `#D01` SHALL NOT be logged. Each row SHALL be flushed to disk as soon as it is written, and disk writes SHALL NOT block the receiving thread.

#### Scenario: Frame logged
- **WHEN** the combined frame `#D01;3415;20;...;#D02;141;...` arrives
- **THEN** a row `<ms>;;#D01;3415;20;...;#D02;141;...` is appended

#### Scenario: Other lines
- **WHEN** an `#I21` line arrives
- **THEN** no row is written

### Requirement: Event column
The Event column SHALL be empty, except that when an event mark has been requested the next logged row SHALL contain `MARK` and the request SHALL then be cleared.

#### Scenario: Mark requested
- **WHEN** a mark is requested and then a frame arrives
- **THEN** that row has `MARK` and the following row has an empty Event

### Requirement: Logging in mock mode
The log SHALL be written for every line from the active source, including replayed lines from the mock source.

#### Scenario: Replay
- **WHEN** the mock source is active
- **THEN** a new log file is created and filled with the replayed frames

### Requirement: Manual event mark
On the Dashboard and the VE calibration screen, pressing Enter or Return SHALL play `datalog.mark_sound` from the start (restarting it if it is playing) and request an event mark for the next logged row. Auto-repeat events SHALL be ignored, so holding the key marks once. The request is a flag, not a counter: several presses before the next frame produce a single `MARK` row. On the Home screen Enter SHALL keep opening the selected screen and SHALL NOT mark.

#### Scenario: Mark during a run
- **WHEN** the user presses Enter on the Dashboard and the next frame arrives
- **THEN** the sound plays and that row has `MARK` in the Event column

#### Scenario: Held key
- **WHEN** the user holds Enter
- **THEN** only one mark is requested

#### Scenario: Two presses before a frame
- **WHEN** the user presses Enter twice before the next frame
- **THEN** only the next row has `MARK`

#### Scenario: Home screen
- **WHEN** the user presses Enter on Home
- **THEN** the selected screen opens and no mark is requested

### Requirement: Clean shutdown of the log
When the app exits, the datalog SHALL write every row it has already received, close the file and finish its writer thread. Closing the datalog more than once SHALL be harmless.

#### Scenario: Rows pending at exit
- **WHEN** frames have been received but not yet written and the app exits
- **THEN** all of them are in the file after shutdown and the file is closed

#### Scenario: Closed twice
- **WHEN** the datalog is closed a second time
- **THEN** nothing happens and no error is raised
