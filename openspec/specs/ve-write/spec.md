# ve-write Specification

## Purpose

Defines how edits made on the VE calibration screen are sent to the ECU: a one-second inactivity delay, row-by-row writes and audible confirmation.

## Requirements

### Requirement: Write delay
Every VE edit (↑, ↓ or reset) SHALL (re)start a 1000 ms single-shot delay. Only when 1000 ms pass without another edit SHALL pending rows be written.

#### Scenario: Burst of edits
- **WHEN** the user presses ↑ five times within one second each
- **THEN** a single write happens 1 second after the last press

### Requirement: Row-by-row write
When the delay elapses, the system SHALL write every pending row, in ascending row order, as the ECU row command for that row (row index + 1) carrying all 16 current raw values of the row. Each row SHALL be marked as sent before its command is queued, so it is not written again unless edited again. A row is written in full, not cell by cell. The write-on-memory command SHALL NOT be sent.

#### Scenario: Two rows edited
- **WHEN** cells in rows 3 and 7 (0-based) are pending
- **THEN** `#F04;…` and `#F08;…` are queued, each with 16 values, in that order

#### Scenario: Not rewritten
- **WHEN** a row was written and not edited since
- **THEN** it is not written again

### Requirement: Nothing to write
When the delay elapses and no row is pending, nothing SHALL be sent and no sound SHALL play.

#### Scenario: Edit undone
- **WHEN** the user raises and then lowers the same cell back to its original value within the delay
- **THEN** no command is sent

### Requirement: Confirmation sound
After queuing at least one row, the system SHALL play the configured `ve_calibration.ve_sound` once, restarting it if it is already playing.

#### Scenario: Batch sent
- **WHEN** one or more rows are written
- **THEN** the VE sound plays once

### Requirement: Reset writes all rows
Because a reset leaves all rows pending, the write that follows a reset SHALL send all 16 rows with the ECU-confirmed original values.

#### Scenario: Reset
- **WHEN** the user presses R and 1 second passes
- **THEN** 16 row commands are queued
