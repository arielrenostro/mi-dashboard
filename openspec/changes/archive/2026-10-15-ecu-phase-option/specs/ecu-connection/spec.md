## ADDED Requirements

### Requirement: Mock parameter block
The mock source SHALL keep a fixed initial `#X02` parameter block (16 values, phase Negativa) and SHALL answer an `#X02` command without arguments by emitting the line `#X02;` followed by the current 16 values joined by `;`. An `#X02` command with 16 arguments SHALL replace the kept block and SHALL NOT emit anything. Commands with a different number of arguments SHALL be ignored. This SHALL NOT affect the replay.

#### Scenario: Request
- **WHEN** `#X02` is sent to the mock without arguments
- **THEN** the mock emits `#X02;` plus the 16 initial values

#### Scenario: Write then request
- **WHEN** `#X02` is sent to the mock with 16 values and then without arguments
- **THEN** the second answer carries the values that were written

#### Scenario: Write is silent
- **WHEN** `#X02` is sent to the mock with 16 values
- **THEN** nothing is emitted

#### Scenario: Wrong argument count
- **WHEN** `#X02` is sent to the mock with 5 values
- **THEN** the kept block does not change
