## MODIFIED Requirements

### Requirement: Line format
A line SHALL end with `\n`; a trailing `\r` SHALL be ignored. A line SHALL be split at `;`, the last item (empty, because every line ends with `;`) SHALL be discarded, and the first item SHALL decide the meaning: `#D` is a data line, `#H` is the header sent once after the device starts, `#M` is a text message, and `#Z` is the device's reply to the zero command (see "Zero acknowledgement"). A data line SHALL carry, after `#D`, exactly seven numeric values in this order: `t_ms`, `pitch` (degrees, positive = nose down), `roll` (degrees, positive = right side down), `ax_g`, `ay_g`, `az_g` and `temp_c`. A command reply SHALL carry, after its tag, exactly one item, the status. A data line with any other number of values or with a value that is not a number SHALL be ignored, and so SHALL a command reply with any other number of items. A line that starts with anything else, such as the replies of the retired `#R` and `#C` commands, SHALL be ignored. Ignored lines SHALL NOT change any state and SHALL NOT raise an error.

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

### Requirement: Device messages
A `#M` line SHALL carry one text after `#M`; the app SHALL keep the latest one for display. No `#M` text SHALL change the zero flag: it follows the command reply only. The texts are uppercase with `_` in place of a space and are shown as they come.

#### Scenario: Latest message kept
- **WHEN** `#M;ENVIE_Z_COM_O_CARRO_EM_SOLO_PLANO_PARA_ZERAR;` arrives
- **THEN** the latest message reads `ENVIE_Z_COM_O_CARRO_EM_SOLO_PLANO_PARA_ZERAR`

#### Scenario: Unknown message
- **WHEN** `#M;COMANDO_DESCONHECIDO;` arrives
- **THEN** the latest message reads `COMANDO_DESCONHECIDO` and no state changes

#### Scenario: Old state texts do nothing
- **WHEN** zeroed is true and `#M;ZERO_REMOVIDO;` arrives
- **THEN** the zero flag stays true and only the latest message changes

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

## ADDED Requirements

### Requirement: Zero flag
The app SHALL keep one flag, `zeroed`, and no angle offset. The flag SHALL become true only when the reply `#Z;OK` arrives (not when the command is sent). The flag SHALL become false when: the port is opened (every time); a `#H` line arrives (the device restarted); a data line has `t_ms` lower than the previous data line (the device restarted); the port is closed. The app SHALL NOT send a zero command by itself at any moment.

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

### Requirement: Zero command
The app SHALL be able to send the zero command (`#Z`), written in uppercase as the command followed by `\n`. It SHALL be sent only while the port is open; otherwise it SHALL be dropped and the caller SHALL be told that it was not sent. The app SHALL NOT send any other command: the gyroscope recalibration (`#C`) and the zero removal (`#R`) no longer exist. The command SHALL be written by the connection's own thread, so the caller never blocks on the serial port. Sending the command SHALL NOT change any state: only the device's reply does (see "Zero acknowledgement").

#### Scenario: Zero
- **WHEN** the port is open and the zero command is requested
- **THEN** `#Z\n` is written to the port

#### Scenario: Port closed
- **WHEN** the port is not open and the zero command is requested
- **THEN** nothing is written and the caller is told that it was not sent

#### Scenario: Sending changes nothing
- **WHEN** `#Z` is written and no reply arrives
- **THEN** `zeroed` stays false

## REMOVED Requirements

### Requirement: Calibration state
**Reason**: The device no longer calibrates a gyroscope, so there is no `calibrating` state, no 10 second timer and no `#C;CALIBRANDO` / `#C;OK` replies.
**Migration**: None. The state shown to the user loses `calibrating` (see "Usable pitch").

### Requirement: Zero state
**Reason**: The reply `#R;OK` and the calibration reply no longer clear the flag, because those commands are gone.
**Migration**: Replaced by "Zero flag".

### Requirement: Signal presence
**Reason**: The tolerance for the pause during a gyroscope calibration is gone with the calibration.
**Migration**: Replaced by "Data stream presence".

### Requirement: Command replies
**Reason**: Only the reply to `#Z` remains; the replies of `#R` and `#C` are gone.
**Migration**: Replaced by "Zero acknowledgement".

### Requirement: Commands to the device
**Reason**: The app sends only the zero command; the recalibration command is gone.
**Migration**: Replaced by "Zero command".
