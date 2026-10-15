# phase-write Specification

## Purpose
Defines how a phase change made on the Options screen reaches the ECU: a one-second inactivity delay, a read-modify-write of the `#X02` parameter block that changes only the phase value, no write to the ECU memory, a confirmation read and the handling of missing or invalid answers.

## Requirements

### Requirement: Write delay
Every phase toggle SHALL (re)start a 1000 ms single-shot delay. Only when 1000 ms pass without another toggle SHALL the app start talking to the ECU.

#### Scenario: Burst of toggles
- **WHEN** the user toggles the phase three times within one second each
- **THEN** the ECU is contacted once, 1 second after the last toggle, with the phase requested by the last toggle

### Requirement: Read before write
When the delay elapses the app SHALL first queue the `#X02` request (no arguments) and SHALL NOT write until a valid `#X02` answer arrives. The block to write SHALL be built from that fresh answer, not from an earlier stored copy.

#### Scenario: Request first
- **WHEN** the delay elapses
- **THEN** exactly one command is queued: `#X02` without arguments

#### Scenario: Fresh block used
- **WHEN** the shared state holds an old `#X02` block and the ECU answers the request with a block whose first value is different
- **THEN** the block written back carries the first value from the answer

### Requirement: Only the phase changes
The block written SHALL have the same 16 values, in the same order, as the answer, except for the phase value (position 11, 0-based, the 12th value after `#X02`), which SHALL be 0 for Negativa or 1 for Positiva. The command SHALL be `#X02` followed by the 16 values joined by `;`.

#### Scenario: Negative to positive
- **WHEN** the ECU answers `#X02;600;400;6;0;117;8000;6100;6300;5;2000;1750;0;1960;2;100;2` and the requested phase is Positiva
- **THEN** the line `#X02;600;400;6;0;117;8000;6100;6300;5;2000;1750;1;1960;2;100;2` is queued

#### Scenario: Positive to negative
- **WHEN** the ECU answers a block with phase value 1 and the requested phase is Negativa
- **THEN** the block written is identical except that position 11 is 0

### Requirement: Already applied
If the answer to the read already has the requested phase, the app SHALL NOT write and SHALL NOT read again; the change counts as applied.

#### Scenario: Toggled back
- **WHEN** the user toggles the phase twice within the delay and the ECU still holds the original phase
- **THEN** only the `#X02` request is queued and the status becomes `Fase aplicada (não gravada na memória)`

### Requirement: Not saved to memory
A phase change SHALL NOT send the write-on-memory command (`#D04`), so the ECU keeps the new phase only until it is power-cycled.

#### Scenario: Complete change
- **WHEN** a phase change goes through the whole sequence
- **THEN** the commands queued are the `#X02` request, the `#X02` write and the confirmation `#X02` request, and no `#D04`

### Requirement: Write sound
Each time the phase block is written to the ECU (the `#X02` command with 16 values is queued), the system SHALL play the configured `ve_calibration.ve_sound` once, restarting it if it is already playing. The sound SHALL play even if the Options screen is no longer visible. It SHALL NOT play for the `#X02` requests (the read and the confirmation), nor when no write is needed because the ECU already holds the requested phase, nor when the sequence fails before the write.

#### Scenario: Block written
- **WHEN** the read answer arrives and the block is written
- **THEN** the sound plays once

#### Scenario: Requests are silent
- **WHEN** the delay elapses and the `#X02` request is queued
- **THEN** no sound plays

#### Scenario: Already applied
- **WHEN** the read answer already has the requested phase
- **THEN** no sound plays

#### Scenario: Failed read
- **WHEN** the read times out or its answer is invalid
- **THEN** no sound plays

#### Scenario: Screen left
- **WHEN** the user toggles the phase and leaves the Options screen before the write
- **THEN** the sound still plays when the block is written

### Requirement: Confirmation read
After queuing the write, the app SHALL queue the `#X02` request again. When that answer arrives, the app SHALL compare its phase value with the requested phase: equal means the change is applied; different means the ECU kept another phase, and the displayed phase SHALL return to the one the ECU reported.

#### Scenario: Applied
- **WHEN** the confirmation answer has the requested phase
- **THEN** the status is `Fase aplicada (não gravada na memória)` and the field shows the requested phase without the pending marker

#### Scenario: Not applied
- **WHEN** the confirmation answer still has the old phase
- **THEN** the status is `A ECU manteve a fase <old phase name>` and the field shows the old phase

### Requirement: Answers are matched by prefix
Only lines starting with `#X02` SHALL be treated as answers. Every valid `#X02` line SHALL be published to the shared state, whether or not a change is in progress.

#### Scenario: Unrelated line
- **WHEN** a line that does not start with `#X02` arrives while a change is waiting for an answer
- **THEN** it is ignored and the change keeps waiting

#### Scenario: Refresh without a change
- **WHEN** a valid `#X02` line arrives and no change is in progress
- **THEN** it is published to the shared state and nothing is written

### Requirement: Invalid or missing answers
An answer SHALL be valid only if it has exactly 16 integer values after the prefix. When the answer to a request (the read or the confirmation) is invalid, nothing further SHALL be queued, the status SHALL be `Resposta #X02 inválida` and the displayed phase SHALL return to the last valid one published; an invalid line SHALL NOT be published to the shared state. When no valid answer arrives within 2000 ms of a request (the read or the confirmation), the status SHALL be `Sem resposta da ECU`, nothing further SHALL be queued and the displayed phase SHALL return to the last one published.

#### Scenario: Wrong value count
- **WHEN** the answer to the read has 15 values
- **THEN** no write is queued and the status is `Resposta #X02 inválida`

#### Scenario: Non-numeric value
- **WHEN** the answer to the read contains a value that is not an integer
- **THEN** no write is queued and the status is `Resposta #X02 inválida`

#### Scenario: Invalid confirmation
- **WHEN** the answer to the confirmation request has 15 values
- **THEN** the status is `Resposta #X02 inválida` and the shared state keeps the previous block

#### Scenario: Read timeout
- **WHEN** 2000 ms pass after the read request without an answer
- **THEN** no write is queued and the status is `Sem resposta da ECU`

#### Scenario: Confirmation timeout
- **WHEN** 2000 ms pass after the confirmation request without an answer
- **THEN** the status is `Sem resposta da ECU` and the displayed phase is the last published one

### Requirement: Toggle while in progress
A toggle made while the app is waiting for an answer SHALL abandon that wait, set the new requested phase (the opposite of the one displayed) and restart the 1000 ms delay, so a new full sequence runs.

#### Scenario: Toggle after the write
- **WHEN** the user toggles while the confirmation answer is pending
- **THEN** the pending wait is dropped and a new sequence starts after 1 second without further toggles
