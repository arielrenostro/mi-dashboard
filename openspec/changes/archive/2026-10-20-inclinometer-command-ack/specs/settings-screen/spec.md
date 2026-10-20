## MODIFIED Requirements

### Requirement: Inclinometer readout
The non-selectable lines SHALL follow the inclinometer. The state line SHALL read `Desligado` (disabled), `Desconectado`, `Calibrando…`, `Sem sinal`, `Conectado, sem zero` or `Conectado, zerado`, for the states `disabled`, `disconnected`, `calibrating`, `no signal`, `not zeroed` and `usable`. The pitch, roll and temperature lines SHALL read `Pitch +1.4°`, `Roll -0.6°` and `Temp 31.4 °C` from the latest valid reading, whether or not the device is zeroed, and `Pitch --`, `Roll --` and `Temp --` when no reading exists or the state is `disabled`, `disconnected` or `no signal`. The device message line SHALL read `Mensagem: <text>` of the latest device message, which is the text of the latest `#M` line or the latest command reply in the form `<CMD>: <STATUS>` (empty when none). The lines SHALL refresh at least every 200 ms while the screen is active.

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
