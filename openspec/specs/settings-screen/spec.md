# settings-screen Specification

## Purpose
Defines the Settings screen, a keyboard-driven list where settings of `config.json` are edited from the driver's seat and where the inclinometer is connected, zeroed and its accelerometer calibrated. Every change is saved to the configuration file at once.

## Requirements

### Requirement: Settings screen layout
The Settings screen (name `settings`) SHALL have a black background, the title `Configurações` in large bold white text, a vertical list of rows grouped under the headings `Giroscópio` and `Ajuste de Ignição`, a status line and the hint `↑↓ Navegar | ←→ Alterar | Enter Executar | Esc Voltar` in gray at the bottom. The selectable rows SHALL be, in this order: under `Giroscópio`, `Porta`, `Conectar` (or `Desconectar`), `Zerar inclinação`, `Calibrar acelerômetro`, `Ver calibração` and `Restaurar calibração`; under `Ajuste de Ignição`, `Inclinação máxima`, `RPM mínimo`, `RPM máximo`, `Estabilização` and `Tempo mínimo do cenário`. Under the gyroscope rows, non-selectable lines SHALL show the inclinometer state, the pitch, the roll, the temperature, the latest device message and the calibration. The selected row SHALL be drawn with white text, a blue border and a translucent blue background, like the selected Home menu item. The status line SHALL show the latest status message (empty when there is none). While the calibration wizard is open (see "Calibration wizard") it SHALL replace the list of rows and the non-selectable lines.

#### Scenario: Initial content
- **WHEN** the Settings screen is shown for the first time
- **THEN** it shows the title `Configurações`, the row `Porta` selected, the eleven selectable rows, the hint and an empty status line

### Requirement: Row navigation
↑ SHALL select the previous selectable row and ↓ the next one, wrapping around at both ends. Auto-repeat events SHALL be ignored. ESC SHALL show the Home screen, except while the calibration wizard is open, when it closes the wizard instead (see "Calibration wizard").

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

#### Scenario: Calibration rows in order
- **WHEN** `Zerar inclinação` is selected and the user presses ↓ three times
- **THEN** `Calibrar acelerômetro`, `Ver calibração` and `Restaurar calibração` are selected in turn

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

### Requirement: Inclinometer readout
The non-selectable lines SHALL follow the inclinometer. The state line SHALL read `Desligado` (disabled), `Desconectado`, `Sem sinal`, `Conectado, sem zero` or `Conectado, zerado`, for the states `disabled`, `disconnected`, `no signal`, `not zeroed` and `usable`. The pitch, roll and temperature lines SHALL read `Pitch +1.4°`, `Roll -0.6°` and `Temp 31.4 °C` from the latest valid reading, whether or not the device is zeroed, and `Pitch --`, `Roll --` and `Temp --` when no reading exists or the state is `disabled`, `disconnected` or `no signal`. The device message line SHALL read `Mensagem: <text>` of the latest device message, which is the text of the latest `#M` line or the latest command reply in the form `<CMD>: <STATUS>` (empty when none). The calibration line SHALL read `Calibração: offset +0.010 -0.020 -0.345 | ganho 1.000 1.000 1.035` from the latest calibration report of the device (offsets X, Y, Z and gains X, Y, Z, with three decimals and a sign on the offsets), and `Calibração: --` when no report exists. The lines SHALL refresh at least every 200 ms while the screen is active.

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

#### Scenario: Calibration reported
- **WHEN** the latest calibration report has the offsets 0.01, -0.02 and -0.345 and the gains 1, 1 and 1.035
- **THEN** the calibration line reads `Calibração: offset +0.010 -0.020 -0.345 | ganho 1.000 1.000 1.035`

#### Scenario: No calibration known
- **WHEN** no calibration report has arrived since the port was opened
- **THEN** the calibration line reads `Calibração: --`

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

### Requirement: Zero row
Enter on `Zerar inclinação` SHALL send the zero command to the inclinometer. When the command could not be sent because the port is not open the status line SHALL read `Giroscópio desconectado`; otherwise it SHALL read `Comando enviado`. The zero command has no speed restriction. The result of the zero command SHALL be visible through the state and the latest device message lines. The screen has no row to recalibrate the device: the inclinometer has no gyroscope to calibrate.

#### Scenario: Zero sent
- **WHEN** the port is open and the user presses Enter on `Zerar inclinação`
- **THEN** the zero command is sent and the status line reads `Comando enviado`

#### Scenario: Zero without a device
- **WHEN** the port is closed and the user presses Enter on `Zerar inclinação`
- **THEN** nothing is sent and the status line reads `Giroscópio desconectado`

### Requirement: Calibration rows
Enter on `Calibrar acelerômetro` SHALL open the calibration wizard (see "Calibration wizard"). Enter on `Ver calibração` SHALL send the calibration report command to the inclinometer; the device's answer appears in the calibration line. Enter on `Restaurar calibração` SHALL NOT send anything the first time: it SHALL arm the restore and show the status `Enter de novo para restaurar`; Enter pressed next on the same row, with no other key in between, SHALL send the calibration restore command. Any other key press, a change of the selected row or leaving the screen SHALL disarm the restore and clear that status message. For each of the three rows, when the port is not open nothing SHALL be sent, the wizard SHALL NOT open, the restore SHALL NOT be armed and the status line SHALL read `Giroscópio desconectado`; when a command was sent the status line SHALL read `Comando enviado`. The calibration commands have no speed restriction. ← and → SHALL do nothing on these rows.

#### Scenario: Open the wizard
- **WHEN** the port is open and the user presses Enter on `Calibrar acelerômetro`
- **THEN** the calibration wizard is shown

#### Scenario: Wizard without a device
- **WHEN** the port is closed and the user presses Enter on `Calibrar acelerômetro`
- **THEN** the wizard is not shown and the status line reads `Giroscópio desconectado`

#### Scenario: View the calibration
- **WHEN** the port is open and the user presses Enter on `Ver calibração`
- **THEN** the calibration report command is sent and the status line reads `Comando enviado`

#### Scenario: View without a device
- **WHEN** the port is closed and the user presses Enter on `Ver calibração`
- **THEN** nothing is sent and the status line reads `Giroscópio desconectado`

#### Scenario: Restore asks for confirmation
- **WHEN** the port is open and the user presses Enter once on `Restaurar calibração`
- **THEN** nothing is sent and the status line reads `Enter de novo para restaurar`

#### Scenario: Restore confirmed
- **WHEN** the user presses Enter twice in a row on `Restaurar calibração`
- **THEN** the calibration restore command is sent once and the status line reads `Comando enviado`

#### Scenario: Restore disarmed by another key
- **WHEN** the user presses Enter on `Restaurar calibração`, then ↓, ↑ and Enter again
- **THEN** nothing is sent, the status line reads `Enter de novo para restaurar` again, and a third Enter sends the restore command

#### Scenario: Restore without a device
- **WHEN** the port is closed and the user presses Enter on `Restaurar calibração`
- **THEN** nothing is sent, the restore is not armed and the status line reads `Giroscópio desconectado`

### Requirement: Calibration wizard
The calibration wizard SHALL guide the six board positions, in this order, each with its capture command: `Eixo Z para cima` (`#KZU`), `Eixo Z para baixo` (`#KZD`), `Eixo X para cima` (`#KXU`), `Eixo X para baixo` (`#KXD`), `Eixo Y para cima` (`#KYU`) and `Eixo Y para baixo` (`#KYD`). While it is open the screen SHALL show, instead of the rows, the title `Calibrar acelerômetro`, the line `Passo <n> de 6`, the instruction of the step (the position name and the sentence `Mantenha a placa parada`), a line with the wizard status and the hint `Enter Capturar | Esc Cancelar`. ↑, ↓, ← and → SHALL do nothing while the wizard is open.

On a step waiting for the user, Enter SHALL send the capture command of the step and the wizard status SHALL read `Capturando…`; Enter and the other keys except ESC SHALL do nothing until the step ends. The step SHALL end, and the wizard SHALL go to the next step, when the device's acknowledgement of that command arrives (see "Calibration progress" in `gyro-connection`). If no acknowledgement arrives within 3 seconds the step SHALL end without advancing, the wizard status SHALL read `Sem resposta do inclinômetro` and Enter SHALL capture the same step again.

After the acknowledgement of the sixth step the wizard status SHALL read `Calculando…` until the calibration outcome arrives. Outcome `saved`: the wizard status SHALL read `Calibração salva` followed by the calibration line, and Enter or ESC SHALL close the wizard. Outcome `invalid`: the wizard status SHALL read `Calibração inválida, repita as posições`, Enter SHALL start again at step 1 and ESC SHALL close the wizard. If no outcome arrives within 3 seconds of the sixth acknowledgement the wizard status SHALL read `Sem resultado da calibração` and it SHALL behave like the outcome `invalid`.

ESC at any moment before the outcome SHALL close the wizard, show the rows again and set the screen status line to `Calibração cancelada`; the wizard never sends anything on its own to undo what the device already captured. If the port is no longer open (the state is `disabled` or `disconnected`) the wizard SHALL close and the status line SHALL read `Giroscópio desconectado`. Opening the wizard again SHALL always start at step 1. Auto-repeat events SHALL be ignored, and key presses in the wizard SHALL NOT be announced to the event marker.

#### Scenario: First step
- **WHEN** the wizard is opened
- **THEN** it shows `Passo 1 de 6`, the instruction `Eixo Z para cima`, the hint `Enter Capturar | Esc Cancelar` and no rows

#### Scenario: Capture sent
- **WHEN** the wizard is on step 1 and the user presses Enter
- **THEN** `#KZU` is sent and the wizard status reads `Capturando…`

#### Scenario: Keys ignored while capturing
- **WHEN** the capture command was sent and the acknowledgement has not arrived and the user presses Enter and ↓
- **THEN** nothing more is sent and the wizard stays on step 1

#### Scenario: Acknowledgement advances
- **WHEN** `#KZU;OK;` arrives while the wizard waits on step 1
- **THEN** the wizard shows `Passo 2 de 6` with the instruction `Eixo Z para baixo` and waits for Enter

#### Scenario: Six steps in order
- **WHEN** the user presses Enter on each step and the device acknowledges each command
- **THEN** the commands sent are `#KZU`, `#KZD`, `#KXU`, `#KXD`, `#KYU` and `#KYD`, in that order

#### Scenario: No acknowledgement
- **WHEN** the capture command was sent and 3 seconds pass without the acknowledgement
- **THEN** the wizard status reads `Sem resposta do inclinômetro`, the step is still step 1 and Enter sends `#KZU` again

#### Scenario: Waiting for the result
- **WHEN** the acknowledgement of the sixth capture arrives
- **THEN** the wizard status reads `Calculando…`

#### Scenario: Calibration saved
- **WHEN** the outcome `saved` and a report with the offsets 0.01, -0.02 and -0.345 and the gains 1, 1 and 1.035 have arrived
- **THEN** the wizard status reads `Calibração salva`, the calibration line is shown, and Enter closes the wizard and shows the rows

#### Scenario: Calibration invalid
- **WHEN** the outcome `invalid` has arrived and the user presses Enter
- **THEN** the wizard shows `Passo 1 de 6` and waits for Enter

#### Scenario: Invalid, then close
- **WHEN** the outcome `invalid` has arrived and the user presses ESC
- **THEN** the rows are shown again

#### Scenario: No result
- **WHEN** 3 seconds pass after the sixth acknowledgement without an outcome
- **THEN** the wizard status reads `Sem resultado da calibração` and Enter starts again at step 1

#### Scenario: Cancel
- **WHEN** the wizard is on step 3 and the user presses ESC
- **THEN** the rows are shown again, the Home screen is not shown and the status line reads `Calibração cancelada`

#### Scenario: Start again after cancelling
- **WHEN** the wizard was cancelled on step 3 and is opened again
- **THEN** it shows `Passo 1 de 6`

#### Scenario: Port lost
- **WHEN** the wizard is open and the port is lost
- **THEN** the rows are shown again and the status line reads `Giroscópio desconectado`

#### Scenario: Held key
- **WHEN** the user holds Enter on a step that waits for the user
- **THEN** the capture command is sent only once

#### Scenario: Keys not announced
- **WHEN** the user presses Enter in the wizard
- **THEN** the key is not announced to the event marker
