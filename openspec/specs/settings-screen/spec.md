# settings-screen Specification

## Purpose
Defines the Settings screen, a keyboard-driven list where settings of `config.json` are edited from the driver's seat and where the inclinometer is connected, zeroed and recalibrated. Every change is saved to the configuration file at once.

## Requirements

### Requirement: Settings screen layout
The Settings screen (name `settings`) SHALL have a black background, the title `Configurações` in large bold white text, a vertical list of rows grouped under the headings `Giroscópio` and `Ajuste de Ignição`, a status line and the hint `↑↓ Navegar | ←→ Alterar | Enter Executar | Esc Voltar` in gray at the bottom. The selectable rows SHALL be, in this order: under `Giroscópio`, `Porta`, `Conectar` (or `Desconectar`), `Zerar inclinação` and `Recalibrar giroscópio`; under `Ajuste de Ignição`, `Inclinação máxima`, `RPM mínimo`, `RPM máximo`, `Estabilização` and `Tempo mínimo do cenário`. Under the gyroscope rows, non-selectable lines SHALL show the inclinometer state, the pitch, the roll, the temperature and the latest device message. The selected row SHALL be drawn with white text, a blue border and a translucent blue background, like the selected Home menu item. The status line SHALL show the latest status message (empty when there is none).

#### Scenario: Initial content
- **WHEN** the Settings screen is shown for the first time
- **THEN** it shows the title `Configurações`, the row `Porta` selected, the nine selectable rows, the hint and an empty status line

### Requirement: Row navigation
↑ SHALL select the previous selectable row and ↓ the next one, wrapping around at both ends. Auto-repeat events SHALL be ignored. ESC SHALL show the Home screen.

#### Scenario: Move down
- **WHEN** `Porta` is selected and the user presses ↓
- **THEN** `Conectar` is selected

#### Scenario: Wrap at the end
- **WHEN** `Tempo mínimo do cenário` is selected and the user presses ↓
- **THEN** `Porta` is selected

#### Scenario: Wrap at the start
- **WHEN** `Porta` is selected and the user presses ↑
- **THEN** `Tempo mínimo do cenário` is selected

#### Scenario: Back to Home
- **WHEN** the user presses ESC
- **THEN** the Home screen is shown

### Requirement: Gyroscope port row
The `Porta` row SHALL show the value of `gyro.port`, or `Nenhuma` when it is empty. ← and → SHALL select the previous and the next choice, without wrapping, from a list that starts with `Nenhuma` followed by the serial ports available on the machine in ascending order. When `gyro.port` names a port that is not available it SHALL also be in the list, shown as `<port> (indisponível)`. The list SHALL be refreshed when the screen becomes active and at every ← or → press. Selecting a choice SHALL set `gyro.port` (`Nenhuma` sets it empty), save it and reconnect as described in `gyro-connection`.

#### Scenario: Ports offered
- **WHEN** the machine has `COM3` and `COM7`, `gyro.port` is empty and the user presses → twice
- **THEN** the row shows `COM3` and then `COM7`, and `gyro.port` is saved as `COM7`

#### Scenario: Choose none
- **WHEN** `gyro.port` is `COM7` and the user presses ← until `Nenhuma` is shown
- **THEN** `gyro.port` is saved as empty and the connection is closed

#### Scenario: Configured port not available
- **WHEN** `gyro.port` is `COM9` and the machine has only `COM3`
- **THEN** the row reads `COM9 (indisponível)` and the choices are `Nenhuma`, `COM3` and `COM9 (indisponível)`

#### Scenario: End of the list
- **WHEN** the last choice is shown and the user presses →
- **THEN** it stays shown

### Requirement: Connect row
The `Conectar` row SHALL read `Desconectar` while the inclinometer port is open. Enter on it SHALL open the port when it is closed and close it when it is open (see "Closed by the user" in `gyro-connection`). When `gyro.port` is empty Enter SHALL do nothing but show the status message `Escolha uma porta`.

#### Scenario: Connect
- **WHEN** the port is configured and closed and the user presses Enter on `Conectar`
- **THEN** the app tries to open the port

#### Scenario: Disconnect
- **WHEN** the port is open and the user presses Enter
- **THEN** the port is closed and the row reads `Conectar`

#### Scenario: No port chosen
- **WHEN** `gyro.port` is empty and the user presses Enter on `Conectar`
- **THEN** the status line reads `Escolha uma porta` and nothing is opened

### Requirement: Zero and recalibrate rows
Enter on `Zerar inclinação` SHALL send the zero command to the inclinometer; Enter on `Recalibrar giroscópio` SHALL send the recalibration command. When the command could not be sent because the port is not open the status line SHALL read `Giroscópio desconectado`; otherwise it SHALL read `Comando enviado`. The recalibration SHALL NOT be sent while the vehicle speed signal (VSS) is known and greater than 0: the status line SHALL then read `Pare o carro para recalibrar`. The zero command has no speed restriction. The result of the zero command and of the recalibration SHALL be visible through the state and the latest device message lines.

#### Scenario: Zero sent
- **WHEN** the port is open and the user presses Enter on `Zerar inclinação`
- **THEN** the zero command is sent and the status line reads `Comando enviado`

#### Scenario: Zero without a device
- **WHEN** the port is closed and the user presses Enter on `Zerar inclinação`
- **THEN** nothing is sent and the status line reads `Giroscópio desconectado`

#### Scenario: Recalibrate stopped
- **WHEN** the port is open, VSS is 0 and the user presses Enter on `Recalibrar giroscópio`
- **THEN** the recalibration command is sent

#### Scenario: Recalibrate while moving
- **WHEN** VSS is 40 and the user presses Enter on `Recalibrar giroscópio`
- **THEN** nothing is sent and the status line reads `Pare o carro para recalibrar`

#### Scenario: Recalibrate with VSS unknown
- **WHEN** no VSS value has been received and the port is open
- **THEN** pressing Enter on `Recalibrar giroscópio` sends the recalibration command

### Requirement: Inclinometer readout
The non-selectable lines SHALL follow the inclinometer. The state line SHALL read `Desligado` (disabled), `Desconectado`, `Calibrando…`, `Sem sinal`, `Conectado, sem zero` or `Conectado, zerado`, for the states `disabled`, `disconnected`, `calibrating`, `no signal`, `not zeroed` and `usable`. The pitch, roll and temperature lines SHALL read `Pitch +1.4°`, `Roll -0.6°` and `Temp 31.4 °C` from the latest valid reading, whether or not the device is zeroed, and `Pitch --`, `Roll --` and `Temp --` when no reading exists or the state is `disabled`, `disconnected` or `no signal`. The device message line SHALL read `Mensagem: <text>` of the latest `#M` message (empty when none). The lines SHALL refresh at least every 200 ms while the screen is active.

#### Scenario: Usable
- **WHEN** the device is zeroed and the latest reading is pitch 1.37, roll -0.62 and temperature 31.4
- **THEN** the lines read `Conectado, zerado`, `Pitch +1.4°`, `Roll -0.6°` and `Temp 31.4 °C`

#### Scenario: Readings before the zero
- **WHEN** the port is open, the device is not zeroed and the latest pitch is 1.37
- **THEN** the state line reads `Conectado, sem zero` and the pitch line reads `Pitch +1.4°`

#### Scenario: No device
- **WHEN** `gyro.port` is empty
- **THEN** the state line reads `Desligado` and the three reading lines read `Pitch --`, `Roll --` and `Temp --`

#### Scenario: Device message
- **WHEN** the latest message is `Zero definido`
- **THEN** the message line reads `Mensagem: Zero definido`

### Requirement: Numeric setting rows
The ignition tuning rows SHALL edit these settings with ← (decrease) and → (increase) by the step shown, clamped to the range shown, without wrapping:

| Row | Setting | Step | Range | Shown as |
|---|---|---|---|---|
| `Inclinação máxima` | `ignition_tuning.max_tilt_deg` | 0.5 | 0.5 to 20 | `3.0°` |
| `RPM mínimo` | `ignition_tuning.rpm_min` | 100 | 500 up to `rpm_max` | `2900 rpm` |
| `RPM máximo` | `ignition_tuning.rpm_max` | 100 | `rpm_min` up to 9000 | `3100 rpm` |
| `Estabilização` | `ignition_tuning.settle_seconds` | 1 | 0 to 60 | `5 s` |
| `Tempo mínimo do cenário` | `ignition_tuning.min_scenario_seconds` | 5 | 5 to 600 | `20 s` |

Enter SHALL do nothing on these rows. Every change SHALL take effect immediately, as described in `ignition-analysis`, and SHALL be saved. A configured value outside its range or off its step SHALL be shown as it is; a press SHALL apply the step to it and clamp the result to the range.

#### Scenario: Increase the tilt limit
- **WHEN** `ignition_tuning.max_tilt_deg` is 3 and the user presses → on `Inclinação máxima`
- **THEN** the row reads `3.5°` and 3.5 is saved

#### Scenario: Lower bound
- **WHEN** `max_tilt_deg` is 0.5 and the user presses ←
- **THEN** it stays 0.5

#### Scenario: Band cannot cross
- **WHEN** `rpm_min` is 3100 and `rpm_max` is 3100 and the user presses → on `RPM mínimo`
- **THEN** `rpm_min` stays 3100

#### Scenario: Maximum RPM bound
- **WHEN** `rpm_max` is 9000 and the user presses →
- **THEN** it stays 9000

#### Scenario: Enter does nothing
- **WHEN** the user presses Enter on `RPM mínimo`
- **THEN** nothing changes

#### Scenario: Value outside the range
- **WHEN** `settle_seconds` is 100 and the user presses ←
- **THEN** the row reads `60 s` (99 clamped to the range) and 60 is saved

### Requirement: Saving
Every change of a setting made on this screen SHALL be saved to the configuration file at once, as described in `app-configuration`. When saving fails the new value SHALL still be applied to the running app, and the status line SHALL read `Não foi possível gravar a configuração` until another status message replaces it. After a successful save the status line SHALL read `Salvo`.

#### Scenario: Saved
- **WHEN** the user changes `Estabilização` from 5 s to 6 s
- **THEN** `ignition_tuning.settle_seconds` is 6 in the running app and in the file, and the status line reads `Salvo`

#### Scenario: Save failure
- **WHEN** the configuration file cannot be written
- **THEN** the new value is used by the running app and the status line reads `Não foi possível gravar a configuração`

### Requirement: Keys and event marker
Auto-repeat events SHALL be ignored on every key. The Settings screen is not a data screen: key presses on it SHALL NOT be announced to the event marker, and it SHALL play no sound.

#### Scenario: Held key
- **WHEN** the user holds → on a numeric row
- **THEN** the value changes only once

#### Scenario: Enter not announced
- **WHEN** the user presses Enter on `Conectar`
- **THEN** the key is not announced to the event marker
