## MODIFIED Requirements

### Requirement: Settings screen layout
The Settings screen (name `settings`) SHALL have a black background, the title `Configurações` in large bold white text, a vertical list of rows grouped under the headings `Giroscópio` and `Ajuste de Ignição`, a status line and the hint `↑↓ Navegar | ←→ Alterar | Enter Executar | Esc Voltar` in gray at the bottom. The selectable rows SHALL be, in this order: under `Giroscópio`, `Porta`, `Conectar` (or `Desconectar`) and `Zerar inclinação`; under `Ajuste de Ignição`, `Inclinação máxima`, `RPM mínimo`, `RPM máximo`, `Estabilização` and `Tempo mínimo do cenário`. Under the gyroscope rows, non-selectable lines SHALL show the inclinometer state, the pitch, the roll, the temperature and the latest device message. The selected row SHALL be drawn with white text, a blue border and a translucent blue background, like the selected Home menu item. The status line SHALL show the latest status message (empty when there is none).

#### Scenario: Initial content
- **WHEN** the Settings screen is shown for the first time
- **THEN** it shows the title `Configurações`, the row `Porta` selected, the eight selectable rows, the hint and an empty status line

### Requirement: Inclinometer readout
The non-selectable lines SHALL follow the inclinometer. The state line SHALL read `Desligado` (disabled), `Desconectado`, `Sem sinal`, `Conectado, sem zero` or `Conectado, zerado`, for the states `disabled`, `disconnected`, `no signal`, `not zeroed` and `usable`. The pitch, roll and temperature lines SHALL read `Pitch +1.4°`, `Roll -0.6°` and `Temp 31.4 °C` from the latest valid reading, whether or not the device is zeroed, and `Pitch --`, `Roll --` and `Temp --` when no reading exists or the state is `disabled`, `disconnected` or `no signal`. The device message line SHALL read `Mensagem: <text>` of the latest device message, which is the text of the latest `#M` line or the latest command reply in the form `<CMD>: <STATUS>` (empty when none). The lines SHALL refresh at least every 200 ms while the screen is active.

#### Scenario: Usable
- **WHEN** the device is zeroed and the latest reading is pitch 1.37, roll -0.62 and temperature 31.4
- **THEN** the lines read `Conectado, zerado`, `Pitch +1.4°`, `Roll -0.6°` and `Temp 31.4 °C`

#### Scenario: Readings before the zero
- **WHEN** the port is open, the device is not zeroed and the latest pitch is 1.37
- **THEN** the state line reads `Conectado, sem zero` and the pitch line reads `Pitch +1.4°`

#### Scenario: No device
- **WHEN** `gyro.port` is empty
- **THEN** the state line reads `Desligado` and the three reading lines read `Pitch --`, `Roll --` and `Temp --`

#### Scenario: Command reply as message
- **WHEN** the latest device message is the reply `Z: OK`
- **THEN** the message line reads `Mensagem: Z: OK`

#### Scenario: Device message
- **WHEN** the latest device message is `COMANDO_DESCONHECIDO`
- **THEN** the message line reads `Mensagem: COMANDO_DESCONHECIDO`

## ADDED Requirements

### Requirement: Zero row
Enter on `Zerar inclinação` SHALL send the zero command to the inclinometer. When the command could not be sent because the port is not open the status line SHALL read `Giroscópio desconectado`; otherwise it SHALL read `Comando enviado`. The zero command has no speed restriction. The result of the zero command SHALL be visible through the state and the latest device message lines. The screen has no row to recalibrate the device: the inclinometer has no gyroscope to calibrate.

#### Scenario: Zero sent
- **WHEN** the port is open and the user presses Enter on `Zerar inclinação`
- **THEN** the zero command is sent and the status line reads `Comando enviado`

#### Scenario: Zero without a device
- **WHEN** the port is closed and the user presses Enter on `Zerar inclinação`
- **THEN** nothing is sent and the status line reads `Giroscópio desconectado`

## REMOVED Requirements

### Requirement: Zero and recalibrate rows
**Reason**: The device no longer has a gyroscope to recalibrate, so the `Recalibrar giroscópio` row, its speed guard (`Pare o carro para recalibrar`) and the `#C` command are removed.
**Migration**: The zero row is kept as "Zero row".
