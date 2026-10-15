## Purpose

Defines the CSV file that records the results of an ignition tuning analysis, so the scenarios of each gear, including the discarded ones, are kept on disk after the session or after a reset.

## ADDED Requirements

### Requirement: One results file per analysis run
The system SHALL record the results of each analysis run in a semicolon-delimited CSV file named `ignition_results_YYYYMMDD_HHMMSS.csv` (local time of the first sample of the run) inside the configured `datalog.path`, with `\n` line endings. A run begins with its first accepted sample and ends with a reset or with the end of the app. The file SHALL NOT be created before the first accepted sample, so opening the screen or a reset without samples creates no file. The first accepted sample after a reset SHALL begin a new run and a new file; the file of the previous run SHALL NOT be changed again.

#### Scenario: First sample
- **WHEN** the first sample of the run is accepted at 2026-10-15 14:03:09 and the results are written
- **THEN** the file `ignition_results_20261015_140309.csv` exists in the datalog directory

#### Scenario: Nothing before a sample
- **WHEN** the screen is opened and left without any accepted sample
- **THEN** no results file is created

#### Scenario: Reset starts a new file
- **WHEN** the user resets and a sample is later accepted at a different time
- **THEN** a second results file with the new time exists and the first one keeps the results of the first run

#### Scenario: Reset without samples
- **WHEN** the user resets before any sample was accepted
- **THEN** no results file is created

### Requirement: Results file content
The file SHALL start with the header `Gear;Offset;RPM min;RPM max;Time s;Samples;Inj. Pulse;MAP;Pedal;Lambda;Ign. Adv.;Knock;Eligible;Inj. Pulse diff %;MAP diff %;Pedal diff %;Best;Discarded`, followed by one row for each scenario of the run, active or discarded, ordered by gear, then offset, then active before discarded. Each row SHALL hold: the gear number; the offset in whole degrees; the configured RPM band; the analysed time in seconds with one decimal; the number of samples; the means of injection time (two decimals), MAP (one), pedal (one), lambda (three) and IGN (one); the knock count; `1` or `0` for eligible; the three percentage differences with one decimal, empty when the scenario is not eligible, has no percentage or is discarded; `1` or `0` for best; and `1` or `0` for discarded. Decimals SHALL use a dot. A discarded scenario SHALL carry the statistics it had when it was discarded, `0` as best and `1` as discarded.

#### Scenario: Header
- **WHEN** the file is read
- **THEN** its first line is the header and it has 18 columns

#### Scenario: Active row
- **WHEN** the active scenario of gear 5 at `+1` has 38.4 seconds, 380 samples, mean injection time 1.08 ms, MAP 45.9, pedal 21.0, lambda 0.912, IGN 33.0, knock 0, is eligible, is the best and has the lowest mean of each compared sensor
- **THEN** its row reads `5;1;2900;3100;38.4;380;1.08;45.9;21.0;0.912;33.0;0;1;0.0;0.0;0.0;1;0`

#### Scenario: Discarded row
- **WHEN** the scenario of gear 4 at `0` was discarded
- **THEN** its row has empty difference columns, Best `0` and Discarded `1`

#### Scenario: Not eligible row
- **WHEN** a scenario has 12 seconds of analysed time
- **THEN** its Eligible is `0` and its difference columns are empty

#### Scenario: Both gears in one file
- **WHEN** gear 4 and gear 5 have scenarios
- **THEN** the file has the rows of gear 4 before the rows of gear 5

#### Scenario: Same key discarded and active
- **WHEN** the scenario of gear 5 at `+1` was discarded and a new one exists at the same gear and offset
- **THEN** the file has two rows for gear 5 and `+1`, the active one first and the discarded one second

### Requirement: When the file is written
Every write SHALL replace the whole file with a complete snapshot of the run, so the file always holds a readable header and the rows of one moment. While the results of the run change, the snapshot SHALL be rewritten at most once every 5 seconds. Pending changes SHALL also be written immediately when the user leaves the screen, when the user resets (a final snapshot of the run before it is cleared) and when the app shuts down. Nothing SHALL be written while nothing changed since the last write.

#### Scenario: Periodic rewrite
- **WHEN** samples keep changing the scenarios for 12 seconds
- **THEN** the file is written at the first sample and then at most once every 5 seconds

#### Scenario: Leaving the screen
- **WHEN** a scenario changed 1 second after the last write and the user presses ESC
- **THEN** the file holds that change immediately

#### Scenario: Final snapshot on reset
- **WHEN** the user presses R with scenarios that changed since the last write
- **THEN** the file of the run holds those scenarios before the analysis is cleared

#### Scenario: Discard is recorded
- **WHEN** the user discards a scenario
- **THEN** the next write holds that scenario as discarded

#### Scenario: Nothing changed
- **WHEN** the analysis is paused or out of range and no scenario changes
- **THEN** the file is not rewritten

### Requirement: Write failures
A failure to create or replace the results file (for example an unusable directory or a file locked by another program) SHALL be logged and SHALL NOT raise to the screen, interrupt the analysis or change any scenario. A failed write SHALL leave the previous complete snapshot intact and SHALL be retried at the next write opportunity.

#### Scenario: Unusable directory
- **WHEN** `datalog.path` is not a directory
- **THEN** the failure is logged and the screen keeps analysing

#### Scenario: Retry
- **WHEN** a write failed and the next write opportunity finds the directory usable
- **THEN** the file is written with the current snapshot

#### Scenario: Failure keeps the previous snapshot
- **WHEN** replacing the file fails
- **THEN** the previously written snapshot is still the content of the file
