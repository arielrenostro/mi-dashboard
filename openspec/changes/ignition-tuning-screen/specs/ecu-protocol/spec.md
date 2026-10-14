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

### Requirement: Response catalog
The system SHALL recognize responses by their prefix: `#D50` (ECU info), `#D01`, `#D02` and `#D03` (telemetry), `#I20` (RPM breakpoints), `#I21` (MAP breakpoints), `#F01` to `#F16` (VE rows) and `#I01` to `#I16` (ignition rows). Breakpoint responses carry 16 integers after the prefix; VE row and ignition row responses carry 16 raw integer values after the prefix.

#### Scenario: Breakpoint response
- **WHEN** the line `#I21;20;30;...` is received
- **THEN** the integers after the prefix are the MAP axis values, ascending

#### Scenario: Ignition row response
- **WHEN** the line `#I05;v1;...;v16` is received
- **THEN** the 16 integers after the prefix are the values of ignition row 5

## ADDED Requirements

### Requirement: Ignition row addressing
Ignition row N of the protocol (`#I0N`) SHALL correspond to row index N-1 of the ignition map, where row index 0 is the lowest MAP breakpoint and index 15 the highest, using the same RPM and MAP axes as the VE map. Raw ignition values SHALL be whole degrees of advance.

#### Scenario: First row
- **WHEN** `#I01` is received
- **THEN** its values are stored as the lowest-MAP ignition row
