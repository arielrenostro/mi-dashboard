## Purpose

Defines the optional inclinometer: the serial link to the Arduino with the MPU-6500, how its lines are read, the states the device can be in, the commands the app sends to it and when its pitch counts as usable. The device filters the angles and keeps the zero itself; the app stores no angle.

## ADDED Requirements

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
A line SHALL end with `\n`; a trailing `\r` SHALL be ignored. A line SHALL be split at `;`, the last item (empty, because every line ends with `;`) SHALL be discarded, and the first item SHALL decide the meaning: `#D` is a data line, `#H` is the header sent once after the device starts, `#M` is a text message. A data line SHALL carry, after `#D`, exactly ten numeric values in this order: `t_ms`, `pitch` (degrees, positive = nose down), `roll` (degrees, positive = right side down), `ax_g`, `ay_g`, `az_g`, `gx_dps`, `gy_dps`, `gz_dps`, `temp_c`. A data line with any other number of values or with a value that is not a number SHALL be ignored. A line that starts with anything else SHALL be ignored. Ignored lines SHALL NOT change any state and SHALL NOT raise an error.

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

#### Scenario: Unknown prefix
- **WHEN** the line `hello;1;2;` arrives
- **THEN** it is ignored

#### Scenario: Header
- **WHEN** the `#H;t_ms;pitch;…;` line arrives
- **THEN** it is not a reading (its effect is described in "Zero state")

### Requirement: Device messages
A `#M` line SHALL carry one text after `#M`; the app SHALL keep the latest one for display. These texts SHALL change the state, compared exactly: `Zero definido` (the device is zeroed), `Zero removido` (the device is not zeroed), `Calibrando...` (the device is calibrating) and `Calibracao ok` (the calibration ended). Any other text SHALL only be kept as the latest message.

#### Scenario: Latest message kept
- **WHEN** `#M;Zero definido;` arrives
- **THEN** the latest message reads `Zero definido`

#### Scenario: Unknown message
- **WHEN** `#M;Comando desconhecido;` arrives
- **THEN** the latest message reads `Comando desconhecido` and no state changes

### Requirement: Zero state
The app SHALL keep one flag, `zeroed`, and no angle offset. The flag SHALL become true only when the message `Zero definido` arrives (not when the command is sent). The flag SHALL become false when: the port is opened (every time); the message `Zero removido` arrives; the message `Calibrando...` arrives; a `#H` line arrives (the device restarted); a data line has `t_ms` lower than the previous data line (the device restarted); the port is closed. The app SHALL NOT send a zero command by itself at any moment.

#### Scenario: Not zeroed at start
- **WHEN** the port has just been opened and data lines arrive
- **THEN** `zeroed` is false

#### Scenario: Zeroed by the device
- **WHEN** `#M;Zero definido;` arrives
- **THEN** `zeroed` is true

#### Scenario: Command sent but not acknowledged
- **WHEN** the zero command is sent and no `Zero definido` message arrives
- **THEN** `zeroed` stays false

#### Scenario: Device restarted
- **WHEN** `zeroed` is true and a `#H` line arrives
- **THEN** `zeroed` becomes false

#### Scenario: Time went back
- **WHEN** `zeroed` is true, a data line has `t_ms` 90000 and the next has `t_ms` 150
- **THEN** `zeroed` becomes false

#### Scenario: Zero removed
- **WHEN** `zeroed` is true and `#M;Zero removido;` arrives
- **THEN** `zeroed` becomes false

#### Scenario: Reconnected
- **WHEN** `zeroed` is true, the port is lost and then opened again
- **THEN** `zeroed` is false

### Requirement: Signal presence
While the port is open, the data stream SHALL be considered absent (`no signal`) when more than 1 second has passed since the last valid data line, or since the port was opened when none has arrived. While the device is calibrating (after `Calibrando...` and before `Calibracao ok`) the data stream SHALL NOT be considered absent for up to 10 seconds from `Calibrando...`; after that the calibration SHALL be treated as ended without `Calibracao ok` and the stream follows the 1 second rule. A valid data line SHALL end `no signal`.

#### Scenario: Stream stops
- **WHEN** the last valid data line is 1.5 seconds old
- **THEN** the state is `no signal`

#### Scenario: Stream resumes
- **WHEN** the state is `no signal` and a valid data line arrives
- **THEN** the signal is present again

#### Scenario: Pause during calibration
- **WHEN** `Calibrando...` arrived 3 seconds ago and no data line arrived since
- **THEN** the state is `calibrating`, not `no signal`

#### Scenario: Calibration never ends
- **WHEN** `Calibrando...` arrived 11 seconds ago and no data line arrived since
- **THEN** the state is `no signal`

### Requirement: Calibration state
After `Calibrando...` the state SHALL be `calibrating` until `Calibracao ok` arrives or 10 seconds pass. `Calibracao ok` SHALL NOT make `zeroed` true: the device does not state that a zero survives the recalibration, so the user zeroes again.

#### Scenario: Calibrating
- **WHEN** `#M;Calibrando...;` arrives
- **THEN** the state is `calibrating` and `zeroed` is false

#### Scenario: Calibration ends
- **WHEN** `#M;Calibracao ok;` arrives after `Calibrando...`
- **THEN** the state is not `calibrating` and `zeroed` is false

### Requirement: Usable pitch
The inclination SHALL be usable only when the port is open, the signal is present, the device is not calibrating and `zeroed` is true. The usable pitch SHALL be the `pitch` of the latest valid data line. When the inclination is not usable there SHALL be no pitch value. The state shown to the user SHALL be exactly one of, in this priority: `disabled`, `disconnected`, `calibrating`, `no signal`, `not zeroed`, `usable`. The roll SHALL NOT take part in this decision.

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

### Requirement: Commands to the device
The app SHALL be able to send the zero command (`#Z`) and the gyroscope recalibration command (`#C`), each written as the command followed by `\n`. A command SHALL be sent only while the port is open; otherwise it SHALL be dropped and the caller SHALL be told that it was not sent. The app SHALL NOT send `#R`. Commands SHALL be written by the connection's own thread, so the caller never blocks on the serial port.

#### Scenario: Zero
- **WHEN** the port is open and the zero command is requested
- **THEN** `#Z\n` is written to the port

#### Scenario: Recalibrate
- **WHEN** the port is open and the recalibration command is requested
- **THEN** `#C\n` is written to the port

#### Scenario: Port closed
- **WHEN** the port is not open and the zero command is requested
- **THEN** nothing is written and the caller is told that it was not sent

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
