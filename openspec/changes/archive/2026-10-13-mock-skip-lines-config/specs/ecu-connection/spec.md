## MODIFIED Requirements

### Requirement: Mock replay
The mock source SHALL, when started, publish a fixed set of breakpoints and a fixed VE map to the shared state. It SHALL skip the first line of the file (the header), then, on its first pass only, skip the number of data lines given by `connection.mock_skip_lines` (default `0`), then emit every following line (trimmed) at one line every 0.1 seconds, and restart from the first data line when it ends without skipping again. Lines that do not start with `#D01` are ignored by downstream consumers. Commands sent to the mock SHALL have no effect on the replay.

#### Scenario: Replay pace
- **WHEN** the mock is running
- **THEN** one line is emitted every 0.1 seconds

#### Scenario: End of file
- **WHEN** the last line has been emitted
- **THEN** the replay restarts from the second line of the file

#### Scenario: Configured skip
- **WHEN** `connection.mock_skip_lines` is `500`
- **THEN** the first emitted line is the 501st data line

#### Scenario: Restart after skip
- **WHEN** the end of the file is reached after a first pass that skipped lines
- **THEN** the replay restarts from the first data line
