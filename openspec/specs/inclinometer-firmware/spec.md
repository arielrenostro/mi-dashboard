# inclinometer-firmware Specification

## Purpose
Defines the firmware of the optional inclinometer (an Arduino with an accelerometer module, an MPU-6050 or MPU-6500 such as the GY-521): the serial link, the boot sequence, the lines it sends, the accelerometer calibration, how it computes and zeroes the angles, and how it acknowledges the commands of the dashboard. The dashboard's side of the same protocol is specified in `gyro-connection`.

## Requirements

### Requirement: Serial link and line framing
The device SHALL talk over the serial port at 115200 baud, 8 data bits, no parity, 1 stop bit. Every line it sends SHALL end with `;` followed by `\n`, and its items SHALL be separated by `;`. The first item SHALL be a tag that starts with `#`. Numbers SHALL use `.` as the decimal separator. Every text item it sends (command statuses and `#M` texts) SHALL contain only the characters `A-Z`, `0-9` and `_` (uppercase, no accents, `_` in place of a space, no `;`).

#### Scenario: Line ends
- **WHEN** the device sends any line
- **THEN** the line ends with `;\n`

#### Scenario: Text characters
- **WHEN** the device sends a status or a `#M` text
- **THEN** the text has only uppercase letters, digits and `_`

### Requirement: Boot sequence
On power-up or reset the device SHALL, in this order: start the serial port and the I2C bus; read the sensor's identity register and send it as one `#M` line `WHO_AM_I_<HEX>` (uppercase hexadecimal, for example `WHO_AM_I_70`); configure the sensor (see "Sensor configuration"); load the accelerometer calibration (see "Accelerometer calibration"); send one `#M` line with the hint `ENVIE_Z_COM_O_CARRO_EM_SOLO_PLANO_PARA_ZERAR`; send the header line `#H;t_ms;pitch;roll;ax_g;ay_g;az_g;temp_c;` once; and start the data stream. The zero SHALL be empty after a boot. When the sensor does not answer on the I2C bus the device SHALL send one `#M` line with the text `MPU_NAO_RESPONDEU_CONFIRA_LIGACAO_E_ENDERECO_0X68_0X69` and then SHALL send nothing else (no header, no data, no command reply) until it is reset. The device SHALL NOT refuse a sensor because of the value of its identity register: an MPU-6050, an MPU-6500 and the GY-521 modules that carry them all work.

#### Scenario: Normal boot
- **WHEN** the device boots with the sensor connected
- **THEN** it sends the `WHO_AM_I_` line, the hint `#M` line, the `#H` line and then data lines, in that order

#### Scenario: Sensor missing
- **WHEN** the device boots and the sensor does not answer
- **THEN** it sends `#M;MPU_NAO_RESPONDEU_CONFIRA_LIGACAO_E_ENDERECO_0X68_0X69;` and no other line follows

#### Scenario: Zero after boot
- **WHEN** the device has just booted
- **THEN** the pitch and roll of the data lines are the filtered angles with no zero applied

#### Scenario: Any chip identity
- **WHEN** the identity register reads `68` (MPU-6050)
- **THEN** the device sends `#M;WHO_AM_I_68;` and boots normally

### Requirement: Sensor configuration
The device SHALL read the sensor at I2C address `0x68` through the registers that MPU-6050 and MPU-6500 have in common, with the accelerometer range at ±2 g and the sensor's internal low-pass filter at about 44 Hz. The gyroscope SHALL NOT take part in anything the device does: no angle, no field of the data line and no command depends on it. The orientation assumed is X = front of the car, Y = left, Z = up.

#### Scenario: Ranges
- **WHEN** the device has booted
- **THEN** the accelerometer range is ±2 g

### Requirement: Data line
Once started, the device SHALL send one data line every 10 ms (100 per second): `#D;t_ms;pitch;roll;ax_g;ay_g;az_g;temp_c;`. `t_ms` SHALL be the milliseconds since boot. `pitch` and `roll` SHALL be in degrees, already minus the zero, with 2 decimals. `ax_g`, `ay_g` and `az_g` SHALL be the calibrated and filtered acceleration in g with 3 decimals. `temp_c` SHALL be the sensor temperature in °C with 1 decimal. The values SHALL be exactly seven, in that order. A command that captures samples (`#Z` and the calibration positions) MAY pause the stream, for no more than 0.8 s each, so that the dashboard (which reports no signal after 1 s) does not notice.

#### Scenario: Line shape
- **WHEN** the device is streaming
- **THEN** each line has the tag `#D` and exactly seven numeric values in the order above

#### Scenario: Rate
- **WHEN** the device is streaming and no command is running
- **THEN** it sends 100 data lines per second

#### Scenario: Time since boot
- **WHEN** two consecutive data lines are sent
- **THEN** the second `t_ms` is not lower than the first

#### Scenario: Pause is short
- **WHEN** `#Z` or a calibration position command runs
- **THEN** no more than 0.8 s passes between two data lines

### Requirement: Command input
The device SHALL read commands from the serial port: a command is a line ended by `\n`; `\r` SHALL be ignored; the letters SHALL be compared after conversion to uppercase; a line SHALL hold at most 15 characters, and a longer line SHALL be discarded up to its `\n` with no reply. Commands are read between data lines, so a command is answered within one sample period (10 ms) when the device is streaming. The commands are `#Z` (set the zero) and the accelerometer calibration family `#K<axis><sense>`, `#KP` and `#KR` (see "Accelerometer calibration"). Any other line, including an empty one and the retired `#C` and `#R`, SHALL be answered with `#M;COMANDO_DESCONHECIDO;`.

#### Scenario: Lowercase accepted
- **WHEN** the device receives `#z\n`
- **THEN** it behaves as for `#Z`

#### Scenario: Carriage return
- **WHEN** the device receives `#Z\r\n`
- **THEN** it behaves as for `#Z`

#### Scenario: Unknown command
- **WHEN** the device receives `#X\n`
- **THEN** it sends `#M;COMANDO_DESCONHECIDO;`

#### Scenario: Retired command
- **WHEN** the device receives `#C\n` or `#R\n`
- **THEN** it sends `#M;COMANDO_DESCONHECIDO;`

#### Scenario: Line too long
- **WHEN** the device receives a line of 40 characters
- **THEN** it sends no reply and the next command is read normally

### Requirement: Messages
The `#M` line SHALL carry one text item: `#M;<TEXT>;`. It SHALL be used only for information that is not a command reply: the chip identity at boot (`WHO_AM_I_<HEX>`), the boot hint, the sensor failure, the unknown command, `CALIBRACAO_SALVA` and `CALIBRACAO_INVALIDA_REPITA_AS_POSICOES` (see "Accelerometer calibration") and `FALHA_DE_LEITURA_DO_SENSOR` (the sensor stopped answering during a capture). No `#M` text SHALL be required for the dashboard to know the state of the zero.

#### Scenario: Message shape
- **WHEN** the device sends a message
- **THEN** the line is `#M;` followed by one text and `;`

### Requirement: Firmware matches the dashboard's protocol
The tags, command names, statuses and the order of the fields of the data and header lines in the firmware SHALL be the ones the dashboard uses, so that the two sides never diverge.

#### Scenario: Contract check
- **WHEN** the automated contract check reads the firmware source
- **THEN** it finds each command, each status and the header line the dashboard uses, and no `#M` text that the dashboard compares

### Requirement: Accelerometer angle estimation
The pitch SHALL be positive with the nose down and the roll SHALL be positive with the right side down. At every sample the device SHALL correct each accelerometer axis with the calibration (`g = (reading - offset) / gain`), pass the three values through a first-order low-pass filter with a time constant of 0.2 s (the filter starts from the first sample, so there is no ramp from zero), and compute `pitch = atan2(-ax, sqrt(ay² + az²))` and `roll = atan2(ay, az)`, in degrees, from the filtered values. Nothing else SHALL take part: no gyroscope, no gate on the magnitude of the acceleration. The angle therefore does not drift.

#### Scenario: Nose down
- **WHEN** the module is still and the front of the car points down by 3 degrees
- **THEN** the pitch settles at +3 (before the zero)

#### Scenario: Right side down
- **WHEN** the module is still and the right side of the car is down by 2 degrees
- **THEN** the roll settles at +2 (before the zero)

#### Scenario: Returns to level
- **WHEN** the module is tilted by 30 degrees, held for a second and put back level
- **THEN** one second later the pitch and roll are within 0.5 degrees of their level values

#### Scenario: Step response
- **WHEN** the module is suddenly tilted by 10 degrees and held
- **THEN** after 0.2 s the pitch has covered about 63 % of the step

#### Scenario: No drift
- **WHEN** the module is left still for ten minutes
- **THEN** the pitch and roll change by less than 0.1 degree

### Requirement: Command acknowledgements
Every known command SHALL be answered by a line of the form `#<CMD>;<STATUS>;`, where `<CMD>` is the command received, sent after the command took effect. The replies are: `#Z;OK;` for `#Z`; `#K<axis><sense>;OK;` for a calibration position, `#KP;OK;` for `#KP` and `#KR;OK;` for `#KR`. The reply SHALL NOT depend on the zero or on any earlier command.

#### Scenario: Zero acknowledged
- **WHEN** the device receives `#Z`
- **THEN** it sends `#Z;OK;`

#### Scenario: Same reply every time
- **WHEN** `#Z` is received twice in a row
- **THEN** each one is answered with `#Z;OK;`

#### Scenario: Calibration position acknowledged
- **WHEN** the device receives `#KZU` and the capture ended
- **THEN** it sends `#KZU;OK;`

### Requirement: Zero on command
On `#Z` the device SHALL average the calibrated acceleration of 25 fresh samples (about 0.12 s, the board must be still), restart the low-pass filter at that average, store the pitch and roll of that average as the zero and answer `#Z;OK;`. From the next data line the pitch and roll SHALL be the filtered angles minus that zero, so they read about 0 at once. The zero SHALL be kept until a reset and SHALL be applied only to the `pitch` and `roll` of the data line.

#### Scenario: Zero applied at once
- **WHEN** the module is still at a pitch of 4.0 and the device receives `#Z`
- **THEN** the next data line has a pitch close to 0

#### Scenario: Zero after a movement
- **WHEN** the module was moved a second ago, is still now and the device receives `#Z`
- **THEN** the next data line has a pitch and a roll close to 0 and they stay there

#### Scenario: Lost on reset
- **WHEN** the device was zeroed and is reset
- **THEN** the zero is empty after the boot

### Requirement: Accelerometer calibration
The device SHALL keep for each axis an offset and a gain, so that a reading is `gain × g + offset`, and SHALL store them in its non-volatile memory (EEPROM) so they survive a reset. Without a stored calibration the offset SHALL be 0 and the gain 1. The calibration is made once, on the bench, in six positions with the board still: the command `#K<axis><sense>` captures the position in which the axis `X`, `Y` or `Z` points up (`U`, reads +1 g) or down (`D`, reads -1 g), by averaging 100 samples (about 0.5 s) of that axis, and answers `#K<axis><sense>;OK;`. When the six positions have been captured the device SHALL compute for each axis `offset = (up + down) / 2` and `gain = (up - down) / 2`, store them, restart the filter, send `#M;CALIBRACAO_SALVA;` and the report line `#K;OFFSET;ox;oy;oz;SCALE;sx;sy;sz;` (4 decimals). When any gain is outside 0.5 to 1.5 the device SHALL discard the six captures, store nothing and send `#M;CALIBRACAO_INVALIDA_REPITA_AS_POSICOES;`. `#KP` SHALL answer `#KP;OK;` and send the report line of the calibration in use. `#KR` SHALL restore offset 0 and gain 1, store them, answer `#KR;OK;` and send the report line. With the calibration made, each face-up axis SHALL read about +1.000 g and the magnitude of the acceleration SHALL be about 1.00 g in any position.

#### Scenario: Position captured
- **WHEN** the board is still with the Z axis up and the device receives `#KZU`
- **THEN** it averages the Z axis for about 0.5 s and answers `#KZU;OK;`

#### Scenario: Six positions saved
- **WHEN** the Z axis read +0.690 up and -1.380 down and the other four positions were captured
- **THEN** the Z offset is -0.345 and its gain 1.035, the device sends `#M;CALIBRACAO_SALVA;` and the report line

#### Scenario: Kept across a reset
- **WHEN** a calibration was saved and the device is reset
- **THEN** `#KP` reports the same offsets and gains

#### Scenario: Restored to the default
- **WHEN** the device receives `#KR`
- **THEN** it answers `#KR;OK;` and `#KP` reports offset 0 and gain 1 on every axis

#### Scenario: Invalid calibration
- **WHEN** the six captures give a gain of 0.2 on one axis
- **THEN** the device sends `#M;CALIBRACAO_INVALIDA_REPITA_AS_POSICOES;` and keeps the previous calibration

#### Scenario: Face up reads one g
- **WHEN** the calibration was saved and the board lies still with any axis up
- **THEN** that axis reads about +1.000 g and the magnitude is about 1.00 g
