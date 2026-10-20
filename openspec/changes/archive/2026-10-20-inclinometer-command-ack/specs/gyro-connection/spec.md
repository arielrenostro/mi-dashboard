## MODIFIED Requirements

### Requirement: Line format
A line SHALL end with `\n`; a trailing `\r` SHALL be ignored. A line SHALL be split at `;`, the last item (empty, because every line ends with `;`) SHALL be discarded, and the first item SHALL decide the meaning: `#D` is a data line, `#H` is the header sent once after the device starts, `#M` is a text message, and `#Z`, `#R` and `#C` are the device's replies to the commands of the same name (see "Command replies"). A data line SHALL carry, after `#D`, exactly ten numeric values in this order: `t_ms`, `pitch` (degrees, positive = nose down), `roll` (degrees, positive = right side down), `ax_g`, `ay_g`, `az_g`, `gx_dps`, `gy_dps`, `gz_dps`, `temp_c`. A command reply SHALL carry, after its tag, exactly one item, the status. A data line with any other number of values or with a value that is not a number SHALL be ignored, and so SHALL a command reply with any other number of items. A line that starts with anything else SHALL be ignored. Ignored lines SHALL NOT change any state and SHALL NOT raise an error.

#### Scenario: Data line
- **WHEN** the line `#D;12840;1.37;-0.62;-0.024;-0.011;1.000;0.12;-0.05;0.03;31.4;` arrives
- **THEN** the latest reading is `t_ms` 12840, pitch 1.37, roll -0.62 and temperature 31.4

#### Scenario: Carriage return
- **WHEN** the same line arrives ending in `\r\n`
- **THEN** it is read as a data line

#### Scenario: Wrong number of values
- **WHEN** a `#D` line carries nine values
- **THEN** it is ignored

#### Scenario: Not a number
- **WHEN** a `#D` line carries `abc` as pitch
- **THEN** it is ignored and the previous reading stays

#### Scenario: Not finite
- **WHEN** a `#D` line carries `nan` as pitch
- **THEN** it is ignored and the previous reading stays

#### Scenario: Unknown prefix
- **WHEN** the line `hello;1;2;` arrives
- **THEN** it is ignored

#### Scenario: Header
- **WHEN** the `#H;t_ms;pitch;…;` line arrives
- **THEN** it is not a reading (its effect is described in "Zero state")

#### Scenario: Command reply
- **WHEN** the line `#Z;OK;` arrives
- **THEN** it is read as the reply `OK` to the command `#Z`

#### Scenario: Command reply with the wrong shape
- **WHEN** the line `#Z;OK;EXTRA;` or `#Z;` arrives
- **THEN** it is ignored

### Requirement: Device messages
A `#M` line SHALL carry one text after `#M`; the app SHALL keep the latest one for display. No `#M` text SHALL change the zero flag or the calibration state: those follow the command replies only. The texts are uppercase with `_` in place of a space and are shown as they come.

#### Scenario: Latest message kept
- **WHEN** `#M;ENVIE_Z_COM_O_CARRO_EM_SOLO_PLANO_PARA_ZERAR;` arrives
- **THEN** the latest message reads `ENVIE_Z_COM_O_CARRO_EM_SOLO_PLANO_PARA_ZERAR`

#### Scenario: Unknown message
- **WHEN** `#M;COMANDO_DESCONHECIDO;` arrives
- **THEN** the latest message reads `COMANDO_DESCONHECIDO` and no state changes

#### Scenario: Old state texts do nothing
- **WHEN** zeroed is true and `#M;ZERO_REMOVIDO;` arrives
- **THEN** the zero flag stays true and only the latest message changes

### Requirement: Zero state
The app SHALL keep one flag, `zeroed`, and no angle offset. The flag SHALL become true only when the reply `#Z;OK` arrives (not when the command is sent). The flag SHALL become false when: the port is opened (every time); the reply `#R;OK` arrives; the reply `#C;CALIBRANDO` arrives; a `#H` line arrives (the device restarted); a data line has `t_ms` lower than the previous data line (the device restarted); the port is closed. The app SHALL NOT send a zero command by itself at any moment.

#### Scenario: Not zeroed at start
- **WHEN** the port has just been opened and data lines arrive
- **THEN** `zeroed` is false

#### Scenario: Zeroed by the device
- **WHEN** `#Z;OK;` arrives
- **THEN** `zeroed` is true

#### Scenario: Command sent but not acknowledged
- **WHEN** the zero command is sent and no `#Z;OK;` reply arrives
- **THEN** `zeroed` stays false

#### Scenario: Device restarted
- **WHEN** `zeroed` is true and a `#H` line arrives
- **THEN** `zeroed` becomes false

#### Scenario: Time went back
- **WHEN** `zeroed` is true, a data line has `t_ms` 90000 and the next has `t_ms` 150
- **THEN** `zeroed` becomes false

#### Scenario: Zero removed
- **WHEN** `zeroed` is true and `#R;OK;` arrives
- **THEN** `zeroed` becomes false

#### Scenario: Reconnected
- **WHEN** `zeroed` is true, the port is lost and then opened again
- **THEN** `zeroed` is false

### Requirement: Signal presence
While the port is open, the data stream SHALL be considered absent (`no signal`) when more than 1 second has passed since the last valid data line, or since the port was opened when none has arrived. While the device is calibrating (after `#C;CALIBRANDO` and before `#C;OK`) the data stream SHALL NOT be considered absent for up to 10 seconds from `#C;CALIBRANDO`; after that the calibration SHALL be treated as ended without `#C;OK` and the stream follows the 1 second rule. A valid data line SHALL end `no signal`.

#### Scenario: Stream stops
- **WHEN** the last valid data line is 1.5 seconds old
- **THEN** the state is `no signal`

#### Scenario: Stream resumes
- **WHEN** the state is `no signal` and a valid data line arrives
- **THEN** the signal is present again

#### Scenario: Pause during calibration
- **WHEN** `#C;CALIBRANDO;` arrived 3 seconds ago and no data line arrived since
- **THEN** the state is `calibrating`, not `no signal`

#### Scenario: Calibration never ends
- **WHEN** `#C;CALIBRANDO;` arrived 11 seconds ago and no data line arrived since
- **THEN** the state is `no signal`

### Requirement: Calibration state
After `#C;CALIBRANDO` the state SHALL be `calibrating` until `#C;OK` arrives or 10 seconds pass. `#C;OK` SHALL NOT make `zeroed` true: the device does not state that a zero survives the recalibration, so the user zeroes again.

#### Scenario: Calibrating
- **WHEN** `#C;CALIBRANDO;` arrives
- **THEN** the state is `calibrating` and `zeroed` is false

#### Scenario: Calibration ends
- **WHEN** `#C;OK;` arrives after `#C;CALIBRANDO;`
- **THEN** the state is not `calibrating` and `zeroed` is false

#### Scenario: Boot calibration
- **WHEN** the device boots and sends `#C;CALIBRANDO;`, `#C;OK;` and then the `#H` line
- **THEN** the state is not `calibrating` after `#C;OK;` and `zeroed` is false

### Requirement: Commands to the device
The app SHALL be able to send the zero command (`#Z`) and the gyroscope recalibration command (`#C`), each written in uppercase as the command followed by `\n`. A command SHALL be sent only while the port is open; otherwise it SHALL be dropped and the caller SHALL be told that it was not sent. The app SHALL NOT send `#R`. Commands SHALL be written by the connection's own thread, so the caller never blocks on the serial port. Sending a command SHALL NOT change any state: only the device's reply does (see "Command replies").

#### Scenario: Zero
- **WHEN** the port is open and the zero command is requested
- **THEN** `#Z\n` is written to the port

#### Scenario: Recalibrate
- **WHEN** the port is open and the recalibration command is requested
- **THEN** `#C\n` is written to the port

#### Scenario: Port closed
- **WHEN** the port is not open and the zero command is requested
- **THEN** nothing is written and the caller is told that it was not sent

#### Scenario: Sending changes nothing
- **WHEN** `#C` is written and no reply arrives
- **THEN** the state is not `calibrating`

## ADDED Requirements

### Requirement: Command replies
The device acknowledges each command with a line `#<CMD>;<STATUS>;`, compared exactly (uppercase). These replies SHALL change the state: `#Z;OK` (the device is zeroed), `#R;OK` (the device is not zeroed), `#C;CALIBRANDO` (the device started a gyroscope calibration) and `#C;OK` (the calibration ended). Any other status of a known command SHALL only be kept as the latest message. Every command reply SHALL also be kept as the latest message, in the form `<CMD>: <STATUS>` with the command letter and no `#` (`Z: OK`, `R: OK`, `C: CALIBRANDO`, `C: OK`); the latest message is the last of the `#M` texts and the command replies to arrive.

#### Scenario: Zero acknowledged
- **WHEN** `#Z;OK;` arrives
- **THEN** the latest message reads `Z: OK`

#### Scenario: Calibration reply as message
- **WHEN** `#C;CALIBRANDO;` arrives
- **THEN** the latest message reads `C: CALIBRANDO`

#### Scenario: Unknown status
- **WHEN** `#Z;ERRO;` arrives
- **THEN** the latest message reads `Z: ERRO` and no state changes

#### Scenario: Not case folded
- **WHEN** `#Z;ok;` arrives
- **THEN** the latest message reads `Z: ok` and `zeroed` does not become true
