## MODIFIED Requirements

### Requirement: Command catalog
The system SHALL define the following commands. A command MAY carry arguments, in which case the wire text is the command text followed by `;` and the arguments joined by `;`.

| Command | Wire text | Purpose |
|---|---|---|
| ECU info | `#D50` | Handshake / identify ECU |
| Streaming stop | `#D00` | Stop telemetry (defined, not used) |
| Streaming start | `#D01` | Start telemetry |
| Write on memory | `#D04` | Persist to ECU memory (defined, not used) |
| Lambda loop close | `#D05` | Close the lambda feedback loop |
| Lambda loop open | `#D06` | Open the lambda feedback loop |
| RPM breakpoints | `#I20` | Request the 16 RPM axis values |
| MAP breakpoints | `#I21` | Request the 16 MAP axis values |
| Parameter block X02 | `#X02` | Request the 16 values of the parameter block; with 16 arguments, write them |
| VE row N (N = 1..16) | `#F01` .. `#F16` | Request VE row N; with 16 arguments, write VE row N |
| Ignition row N (N = 1..16) | `#I01` .. `#I16` | Request ignition row N; with 16 arguments, write ignition row N |

#### Scenario: Command without arguments
- **WHEN** the lambda loop open command is sent
- **THEN** the line `#D06` is written

#### Scenario: Command with arguments
- **WHEN** VE row 5 is written with 16 raw values
- **THEN** the line `#F05;v1;v2;...;v16` is written

#### Scenario: Ignition row write
- **WHEN** ignition row 3 is written with 16 raw values
- **THEN** the line `#I03;v1;v2;...;v16` is written

#### Scenario: Parameter block request
- **WHEN** the parameter block command is sent without arguments
- **THEN** the line `#X02` is written

#### Scenario: Parameter block write
- **WHEN** the parameter block command is sent with 16 values
- **THEN** the line `#X02;v1;v2;...;v16` is written

### Requirement: Response catalog
The system SHALL recognize responses by their prefix: `#D50` (ECU info), `#D01`, `#D02` and `#D03` (telemetry), `#I20` (RPM breakpoints), `#I21` (MAP breakpoints), `#X02` (parameter block), `#F01` to `#F16` (VE rows) and `#I01` to `#I16` (ignition rows). Breakpoint responses carry 16 integers after the prefix; parameter block, VE row and ignition row responses carry 16 raw integer values after the prefix.

#### Scenario: Breakpoint response
- **WHEN** the line `#I21;20;30;...` is received
- **THEN** the integers after the prefix are the MAP axis values, ascending

#### Scenario: Ignition row response
- **WHEN** the line `#I05;v1;...;v16` is received
- **THEN** the 16 integers after the prefix are the values of ignition row 5

#### Scenario: Parameter block response
- **WHEN** the line `#X02;v1;...;v16` is received
- **THEN** the 16 integers after the prefix are the values of the parameter block

## ADDED Requirements

### Requirement: Engine phase in the parameter block
Position 11 (0-based, the 12th value after the `#X02` prefix) of the parameter block SHALL hold the engine phase: `0` means Negativa and `1` means Positiva. The other 15 values of the block are not interpreted by the app and SHALL be preserved unchanged when the block is written back.

#### Scenario: Phase values
- **WHEN** the block `#X02;600;400;6;0;117;8000;6100;6300;5;2000;1750;0;1960;2;100;2` is received
- **THEN** its phase is Negativa

#### Scenario: Positive phase
- **WHEN** the same block is received with `1` in position 11
- **THEN** its phase is Positiva
