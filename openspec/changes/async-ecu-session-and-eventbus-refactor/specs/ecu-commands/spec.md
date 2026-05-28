## ADDED Requirements

### Requirement: EcuCommand enum defines all commands with response contracts
`EcuCommand` SHALL be an enum where each entry defines: `cmd` (wire string), `description`, and `response_contract: ResponseContract`. `ResponseContract` is an enum with values `ECHO_FULL` (SetData), `ECHO_CMD_ONLY` (SetState), and `DATA_RESPONSE` (GetData).

#### Scenario: SetData command expects full echo
- **WHEN** `EcuCommand.SET_VE_ROW` has `response_contract = ResponseContract.ECHO_FULL`
- **THEN** `EcuSession` SHALL consider the response matched only when the full command+args line is received

#### Scenario: SetState command expects command-only echo
- **WHEN** `EcuCommand.OPEN_LOOP` has `response_contract = ResponseContract.ECHO_CMD_ONLY`
- **THEN** `EcuSession` SHALL consider the response matched when the response line starts with the command code and has no additional payload

#### Scenario: GetData command expects data payload in response
- **WHEN** `EcuCommand.FETCH_VE` has `response_contract = ResponseContract.DATA_RESPONSE`
- **THEN** `EcuSession` SHALL consider the response matched when the response line starts with the command code followed by data

### Requirement: EcuSession exposes typed command methods
`EcuSession` SHALL expose high-level methods for each known command, hiding raw string formatting from callers:
- `open_loop() -> None`
- `close_loop() -> None`
- `fetch_ve() -> list[list[float]]`
- `fetch_ignition() -> list[list[float]]`
- `set_ve_row(row: int, values: list[float]) -> None`
- `set_ignition_row(row: int, values: list[float]) -> None`

Each method SHALL call `send_command()` internally and parse the response according to its contract.

#### Scenario: open_loop sends correct command and awaits echo
- **WHEN** `session.open_loop()` is called
- **THEN** the wire string `"#F10\n"` SHALL be sent and the method SHALL block until `#F10` is received

#### Scenario: fetch_ve returns parsed map data
- **WHEN** `session.fetch_ve()` is called and the ECU responds with `#F02;v1;v2;...`
- **THEN** the method SHALL return a parsed 16×16 matrix of float values

#### Scenario: set_ve_row sends row data and awaits full echo
- **WHEN** `session.set_ve_row(3, [80.0, 81.5, ...])` is called
- **THEN** the wire string `"#F01;3;80.0;81.5;...\n"` SHALL be sent and the method SHALL block until the ECU echoes the same string

### Requirement: EcuCommand enum covers all commands from the existing protocol
All commands currently defined in `EcuCommand` (ECU_INFO, STREAMING_START, OPEN_LOOP, CLOSE_LOOP, FETCH_VE, SET_VE_ROW, FETCH_IGNITION, SET_IGNITION_ROW) SHALL be present with appropriate contracts. Wire strings SHALL remain identical.

#### Scenario: Existing wire strings are preserved
- **WHEN** any existing command is sent after the refactor
- **THEN** the wire string sent over serial SHALL be byte-for-byte identical to the pre-refactor implementation
