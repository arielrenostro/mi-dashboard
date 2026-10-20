## MODIFIED Requirements

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

## ADDED Requirements

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

## REMOVED Requirements

### Requirement: Zero command
**Reason**: The app now sends more than the zero command (the calibration commands), so "the only command" no longer holds.
**Migration**: Replaced by "Commands to the device", which keeps every behavior of the zero command (open-port rule, uppercase with `\n`, own thread, sending changes nothing).
