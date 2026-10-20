# gyro-connection Specification

## Purpose
Defines the optional inclinometer: the serial link to the Arduino with the accelerometer module, how its lines are read, the states the device can be in, the commands the app sends to it (the zero and the accelerometer calibration) and when its pitch counts as usable. The device filters the angles and keeps the zero itself; the app stores no angle.

## Requirements

### Requirement: Optional device on a configured port
The inclinometer SHALL be used only when `gyro.port` is not empty. With an empty `gyro.port` the state SHALL be `disabled`, no serial port SHALL be opened and no command SHALL be sent. The link is serial 115200 baud, 8 data bits, no parity, 1 stop bit; the baud rate is not configurable.

#### Scenario: No port configured
- **WHEN** `gyro.port` is empty
- **THEN** the state is `disabled` and no port is opened

#### Scenario: Port configured
- **WHEN** `gyro.port` is `COM7`
- **THEN** the app tries to open `COM7` at 115200 baud, 8N1

### Requirement: Automatic connection and retry
While `gyro.port` is not empty and the port is not open, the app SHALL try to open it right away and again every 2 seconds, without any user action. A failure to open the port, or a port that disappears while open, SHALL leave the state `disconnected`, SHALL be retried the same way and SHALL NOT be reported through the ECU connection error overlay nor affect the ECU connection. Changing `gyro.port` SHALL close the port in use and, when the new value is not empty, open the new one. The user MAY also close the connection (`Desconectar`) and open it again (`Conectar`) from the Settings screen; a connection closed by the user SHALL stay closed until the user connects again or changes the port.

#### Scenario: Port absent at startup
- **WHEN** the app starts with `gyro.port` set to a port that does not exist
- **THEN** the state is `disconnected` and the open is retried every 2 seconds

#### Scenario: Device appears later
- **WHEN** the port did not exist at startup and exists 10 seconds later
- **THEN** the port is opened by the next retry without any user action

#### Scenario: Port lost
- **WHEN** reading the open port raises an error
- **THEN** the port is closed, the state is `disconnected` and the open is retried every 2 seconds

#### Scenario: Port changed
- **WHEN** `gyro.port` changes from `COM7` to `COM9`
- **THEN** `COM7` is closed and `COM9` is opened

#### Scenario: Port set to none
- **WHEN** `gyro.port` changes to empty
- **THEN** the open port is closed, the state is `disabled` and no retry happens

#### Scenario: Closed by the user
- **WHEN** the user disconnects
- **THEN** the port is closed and is not reopened by the retry until the user connects again

#### Scenario: ECU unaffected
- **WHEN** the inclinometer port cannot be opened
- **THEN** the ECU connection keeps working and no error overlay is shown

### Requirement: Line format
A line SHALL end with `\n`; a trailing `\r` SHALL be ignored. A line SHALL be split at `;`, the last item (empty, because every line ends with `;`) SHALL be discarded, and the first item SHALL decide the meaning: `#D` is a data line, `#H` is the header sent once after the device starts, `#M` is a text message, `#Z` is the device's reply to the zero command (see "Zero acknowledgement"), `#KXU`, `#KXD`, `#KYU`, `#KYD`, `#KZU`, `#KZD`, `#KP` and `#KR` are the device's replies to the calibration commands of the same name (see "Calibration acknowledgements"), and `#K` is the calibration report (see "Calibration progress"). A data line SHALL carry, after `#D`, exactly seven numeric values in this order: `t_ms`, `pitch` (degrees, positive = nose down), `roll` (degrees, positive = right side down), `ax_g`, `ay_g`, `az_g` and `temp_c`. A command reply SHALL carry, after its tag, exactly one item, the status. A calibration report SHALL carry, after `#K`, exactly the items `OFFSET`, three numbers, `SCALE` and three numbers, in that order. A data line with any other number of values or with a value that is not a number SHALL be ignored, and so SHALL a command reply with any other number of items and a calibration report of any other shape (including a number that is not finite). A line that starts with anything else, such as the replies of the retired `#R` and `#C` commands, SHALL be ignored. Ignored lines SHALL NOT change any state and SHALL NOT raise an error.

#### Scenario: Data line
- **WHEN** the line `#D;12840;1.37;-0.62;-0.024;-0.011;1.000;31.4;` arrives
- **THEN** the latest reading is `t_ms` 12840, pitch 1.37, roll -0.62 and temperature 31.4

#### Scenario: Carriage return
- **WHEN** the same line arrives ending in `\r\n`
- **THEN** it is read as a data line

#### Scenario: Wrong number of values
- **WHEN** a `#D` line carries six values, or the ten values of the old format
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
- **THEN** it is not a reading (its effect is described in "Zero flag")

#### Scenario: Command reply
- **WHEN** the line `#Z;OK;` arrives
- **THEN** it is read as the reply `OK` to the command `#Z`

#### Scenario: Command reply with the wrong shape
- **WHEN** the line `#Z;OK;EXTRA;` or `#Z;` arrives
- **THEN** it is ignored

#### Scenario: Retired replies
- **WHEN** the line `#C;OK;` or `#R;OK;` arrives
- **THEN** it is ignored

#### Scenario: Calibration reply
- **WHEN** the line `#KZU;OK;` arrives
- **THEN** it is read as the reply `OK` to the command `#KZU`

#### Scenario: Calibration reply with an unknown axis
- **WHEN** the line `#KQU;OK;` arrives
- **THEN** it is ignored

#### Scenario: Calibration report
- **WHEN** the line `#K;OFFSET;0.0100;-0.0200;-0.3450;SCALE;1.0000;1.0000;1.0350;` arrives
- **THEN** it is read as a calibration report with the offsets 0.01, -0.02 and -0.345 and the gains 1, 1 and 1.035

#### Scenario: Calibration report with the wrong shape
- **WHEN** a `#K` line carries five numbers, or `SCALE` before `OFFSET`, or `nan` as a number
- **THEN** it is ignored

### Requirement: Device messages
A `#M` line SHALL carry one text after `#M`; the app SHALL keep the latest one for display. No `#M` text SHALL change the zero flag, except `CALIBRACAO_SALVA`, which clears it (see "Zero flag"); the two calibration texts `CALIBRACAO_SALVA` and `CALIBRACAO_INVALIDA_REPITA_AS_POSICOES` also set the calibration outcome (see "Calibration progress"). The texts are uppercase with `_` in place of a space and are shown as they come.

#### Scenario: Latest message kept
- **WHEN** `#M;ENVIE_Z_COM_O_CARRO_EM_SOLO_PLANO_PARA_ZERAR;` arrives
- **THEN** the latest message reads `ENVIE_Z_COM_O_CARRO_EM_SOLO_PLANO_PARA_ZERAR`

#### Scenario: Unknown message
- **WHEN** `#M;COMANDO_DESCONHECIDO;` arrives
- **THEN** the latest message reads `COMANDO_DESCONHECIDO` and no state changes

#### Scenario: Old state texts do nothing
- **WHEN** zeroed is true and `#M;ZERO_REMOVIDO;` arrives
- **THEN** the zero flag stays true and only the latest message changes

#### Scenario: Calibration text is also a message
- **WHEN** `#M;CALIBRACAO_INVALIDA_REPITA_AS_POSICOES;` arrives
- **THEN** the latest message reads `CALIBRACAO_INVALIDA_REPITA_AS_POSICOES`

### Requirement: Usable pitch
The inclination SHALL be usable only when the port is open, the signal is present and `zeroed` is true. The usable pitch SHALL be the `pitch` of the latest valid data line. When the inclination is not usable there SHALL be no pitch value. The state shown to the user SHALL be exactly one of, in this priority: `disabled`, `disconnected`, `no signal`, `not zeroed`, `usable`. The roll SHALL NOT take part in this decision.

#### Scenario: Usable
- **WHEN** the port is open, data arrives at 100 Hz, the device was zeroed and the latest pitch is 1.37
- **THEN** the state is `usable` and the pitch is 1.37

#### Scenario: Not zeroed
- **WHEN** the port is open, data arrives and `zeroed` is false
- **THEN** the state is `not zeroed` and there is no pitch value

#### Scenario: Priority
- **WHEN** the port is open, `zeroed` is false and no data arrives for 2 seconds
- **THEN** the state is `no signal`

#### Scenario: Roll ignored
- **WHEN** the device is zeroed and the latest roll is 12 degrees
- **THEN** the state is `usable`

### Requirement: Available ports
The app SHALL be able to list the serial ports available on the machine, by name, so the Settings screen can offer them. Listing SHALL NOT open any port.

#### Scenario: Two ports
- **WHEN** the system reports `COM3` and `COM7`
- **THEN** the list is `COM3`, `COM7`

### Requirement: Readings for display
The latest valid reading (pitch, roll and temperature), the state and the latest device message SHALL be available at any moment without blocking, and a change of state or of the latest message SHALL be announced so the screens can follow it. The announcement SHALL NOT happen once per data line.

#### Scenario: State change announced
- **WHEN** the state changes from `not zeroed` to `usable`
- **THEN** the change is announced once

#### Scenario: Data lines are not announced
- **WHEN** 100 valid data lines arrive and nothing else changes
- **THEN** no announcement is made

### Requirement: Zero flag
The app SHALL keep one flag, `zeroed`, and no angle offset. The flag SHALL become true only when the reply `#Z;OK` arrives (not when the command is sent). The flag SHALL become false when: the port is opened (every time); a `#H` line arrives (the device restarted); a data line has `t_ms` lower than the previous data line (the device restarted); the port is closed; the reply `#KR;OK` arrives (the calibration was restored); the message `CALIBRACAO_SALVA` arrives (a calibration was saved). The last two clear the flag because the device keeps the pitch and roll zero it took with the previous calibration, so the user must zero again. An invalid calibration (`CALIBRACAO_INVALIDA_REPITA_AS_POSICOES`) changes nothing in the device and SHALL NOT clear the flag. The app SHALL NOT send a zero command by itself at any moment.

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

#### Scenario: Reconnected
- **WHEN** `zeroed` is true, the port is lost and then opened again
- **THEN** `zeroed` is false

#### Scenario: Calibration saved
- **WHEN** `zeroed` is true and `#M;CALIBRACAO_SALVA;` arrives
- **THEN** `zeroed` becomes false

#### Scenario: Calibration restored
- **WHEN** `zeroed` is true and `#KR;OK;` arrives
- **THEN** `zeroed` becomes false

#### Scenario: Calibration invalid
- **WHEN** `zeroed` is true and `#M;CALIBRACAO_INVALIDA_REPITA_AS_POSICOES;` arrives
- **THEN** `zeroed` stays true

#### Scenario: Calibration capture
- **WHEN** `zeroed` is true and `#KZU;OK;` arrives
- **THEN** `zeroed` stays true

### Requirement: Data stream presence
While the port is open, the data stream SHALL be considered absent (`no signal`) when more than 1 second has passed since the last valid data line, or since the port was opened when none has arrived. A valid data line SHALL end `no signal`. The device pauses the stream for less than 1 second at most (see `inclinometer-firmware`, "Data line"), so no tolerance exists.

#### Scenario: Stream stops
- **WHEN** the last valid data line is 1.5 seconds old
- **THEN** the state is `no signal`

#### Scenario: Stream resumes
- **WHEN** the state is `no signal` and a valid data line arrives
- **THEN** the signal is present again

#### Scenario: Short pause
- **WHEN** the last valid data line is 0.8 seconds old
- **THEN** the signal is still present

### Requirement: Zero acknowledgement
The device acknowledges the zero command with the line `#Z;OK;`, compared exactly (uppercase). That reply SHALL make `zeroed` true. Any other status of `#Z` SHALL only be kept as the latest message. Every `#Z` reply SHALL also be kept as the latest message, in the form `<CMD>: <STATUS>` with the command letter and no `#` (`Z: OK`); the latest message is the last of the `#M` texts and the `#Z` replies to arrive.

#### Scenario: Zero acknowledged
- **WHEN** `#Z;OK;` arrives
- **THEN** the latest message reads `Z: OK`

#### Scenario: Unknown status
- **WHEN** `#Z;ERRO;` arrives
- **THEN** the latest message reads `Z: ERRO` and no state changes

#### Scenario: Not case folded
- **WHEN** `#Z;ok;` arrives
- **THEN** the latest message reads `Z: ok` and `zeroed` does not become true

### Requirement: Calibration acknowledgements
The device acknowledges each calibration command (the six captures, `#KP` and `#KR`) with the line `#<CMD>;OK;`, compared exactly (uppercase). Every such reply, whatever its status, SHALL be kept as the latest message in the form `<CMD>: <STATUS>` with the command text and no `#` (`KZU: OK`, `KP: OK`, `KR: OK`). Only the status `OK` has an effect on the state (see "Calibration progress" and "Zero flag"); any other status SHALL only be kept as the latest message.

#### Scenario: Capture acknowledged as message
- **WHEN** `#KZU;OK;` arrives
- **THEN** the latest message reads `KZU: OK`

#### Scenario: Unknown status
- **WHEN** `#KZU;ERRO;` arrives
- **THEN** the latest message reads `KZU: ERRO` and the calibration progress does not change

#### Scenario: Not case folded
- **WHEN** `#KZU;ok;` arrives
- **THEN** the latest message reads `KZU: ok` and the calibration progress does not change

### Requirement: Calibration progress
While the port is open the app SHALL track three things: the capture commands the device acknowledged since the progress was last cleared (`acknowledged`), the outcome of the latest calibration (`saved`, `invalid` or none) and the latest calibration report (three offsets and three gains, or none). A reply `OK` to a capture command (`#KXU`, `#KXD`, `#KYU`, `#KYD`, `#KZU` or `#KZD`) SHALL add that command to `acknowledged` and clear the outcome. The message `CALIBRACAO_SALVA` SHALL set the outcome to `saved` and `CALIBRACAO_INVALIDA_REPITA_AS_POSICOES` SHALL set it to `invalid`; both SHALL clear `acknowledged`. A calibration report SHALL replace the latest report. The reply `#KR;OK` SHALL clear `acknowledged` and the outcome. Opening or closing the port SHALL clear all three. The three SHALL be available at any moment without blocking, and a change of any of them SHALL be announced like a change of state, never once per data line. The roll, the pitch and the usable pitch SHALL NOT depend on them.

#### Scenario: Capture acknowledged
- **WHEN** `#KZU;OK;` and then `#KZD;OK;` arrive
- **THEN** `acknowledged` holds `#KZU` and `#KZD` and the outcome is none

#### Scenario: Calibration saved
- **WHEN** the six capture replies, `#M;CALIBRACAO_SALVA;` and a calibration report arrive
- **THEN** the outcome is `saved`, `acknowledged` is empty and the latest report is the one received

#### Scenario: Calibration invalid
- **WHEN** the six capture replies and `#M;CALIBRACAO_INVALIDA_REPITA_AS_POSICOES;` arrive
- **THEN** the outcome is `invalid`, `acknowledged` is empty and the latest report is unchanged

#### Scenario: New capture clears the outcome
- **WHEN** the outcome is `saved` and `#KXU;OK;` arrives
- **THEN** the outcome is none and `acknowledged` holds `#KXU`

#### Scenario: Report requested
- **WHEN** `#KP;OK;` and a calibration report arrive
- **THEN** the latest report is the one received and nothing else changes

#### Scenario: Restored
- **WHEN** `acknowledged` holds `#KZU`, the outcome is `saved` and `#KR;OK;` arrives
- **THEN** `acknowledged` is empty and the outcome is none

#### Scenario: Port reopened
- **WHEN** the port is lost with a report, an outcome and acknowledged captures, and is opened again
- **THEN** the report is none, the outcome is none and `acknowledged` is empty

#### Scenario: Change announced
- **WHEN** a calibration report arrives while data lines keep arriving
- **THEN** the change is announced once

### Requirement: Commands to the device
The app SHALL be able to send these commands, each written in uppercase as the command followed by `\n`: the zero command `#Z`; the six calibration capture commands `#KXU`, `#KXD`, `#KYU`, `#KYD`, `#KZU` and `#KZD`; the calibration report command `#KP`; and the calibration restore command `#KR`. It SHALL NOT send any other command: the gyroscope recalibration (`#C`) and the zero removal (`#R`) no longer exist. A command SHALL be sent only while the port is open; otherwise it SHALL be dropped and the caller SHALL be told that it was not sent. Commands SHALL be written by the connection's own thread, so the caller never blocks on the serial port. Sending a command SHALL NOT change any state: only the device's replies do (see "Zero acknowledgement" and "Calibration acknowledgements"). The app SHALL send a calibration command only at the user's request.

#### Scenario: Zero
- **WHEN** the port is open and the zero command is requested
- **THEN** `#Z\n` is written to the port

#### Scenario: Capture
- **WHEN** the port is open and the capture command `#KZU` is requested
- **THEN** `#KZU\n` is written to the port

#### Scenario: Report
- **WHEN** the port is open and the calibration report is requested
- **THEN** `#KP\n` is written to the port

#### Scenario: Restore
- **WHEN** the port is open and the calibration restore is requested
- **THEN** `#KR\n` is written to the port

#### Scenario: Port closed
- **WHEN** the port is not open and a command is requested
- **THEN** nothing is written and the caller is told that it was not sent

#### Scenario: Sending changes nothing
- **WHEN** `#KZU` is written and no reply arrives
- **THEN** the calibration progress is unchanged and `zeroed` is unchanged

#### Scenario: No other command
- **WHEN** the commands the app can send are listed
- **THEN** they are exactly `#Z`, `#KXU`, `#KXD`, `#KYU`, `#KYD`, `#KZU`, `#KZD`, `#KP` and `#KR`
