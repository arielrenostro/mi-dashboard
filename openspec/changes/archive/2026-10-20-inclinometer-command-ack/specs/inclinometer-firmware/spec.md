## Purpose

Defines the firmware of the optional inclinometer (an Arduino with an MPU-6500): the serial link, the boot sequence, the lines it sends, how it estimates and zeroes the angles, and how it acknowledges the commands of the dashboard. The dashboard's side of the same protocol is specified in `gyro-connection`.

## ADDED Requirements

### Requirement: Serial link and line framing
The device SHALL talk over the serial port at 115200 baud, 8 data bits, no parity, 1 stop bit. Every line it sends SHALL end with `;` followed by `\n`, and its items SHALL be separated by `;`. The first item SHALL be a tag that starts with `#`. Numbers SHALL use `.` as the decimal separator. Every text item it sends (command statuses and `#M` texts) SHALL contain only the characters `A-Z`, `0-9` and `_` (uppercase, no accents, `_` in place of a space, no `;`).

#### Scenario: Line ends
- **WHEN** the device sends any line
- **THEN** the line ends with `;\n`

#### Scenario: Text characters
- **WHEN** the device sends a status or a `#M` text
- **THEN** the text has only uppercase letters, digits and `_`

### Requirement: Boot sequence
On power-up or reset the device SHALL, in this order: start the serial port and the I2C bus; initialise the sensor; configure it (see "Sensor configuration"); calibrate the gyroscope (see "Gyroscope calibration"); send one `#M` line with the hint `ENVIE_Z_COM_O_CARRO_EM_SOLO_PLANO_PARA_ZERAR`; send the header line `#H;t_ms;pitch;roll;ax_g;ay_g;az_g;gx_dps;gy_dps;gz_dps;temp_c;` once; and start the data stream. The zero SHALL be empty after a boot. When the sensor does not answer at initialisation the device SHALL send one `#M` line with the text `MPU_NAO_RESPONDEU_CONFIRA_LIGACAO_E_ENDERECO_0X68_0X69` and then SHALL send nothing else (no header, no data, no command reply) until it is reset.

#### Scenario: Normal boot
- **WHEN** the device boots with the sensor connected
- **THEN** it sends `#C;CALIBRANDO;`, `#C;OK;`, the hint `#M` line, the `#H` line and then data lines, in that order

#### Scenario: Sensor missing
- **WHEN** the device boots and the sensor does not answer
- **THEN** it sends `#M;MPU_NAO_RESPONDEU_CONFIRA_LIGACAO_E_ENDERECO_0X68_0X69;` and no other line follows

#### Scenario: Zero after boot
- **WHEN** the device has just booted
- **THEN** the pitch and roll of the data lines are the filtered angles with no zero applied

### Requirement: Sensor configuration
The device SHALL read the MPU-6500 at I2C address `0x68` with the gyroscope range at ±500 °/s, the accelerometer range at ±2 g, and the internal low-pass filters of both enabled at about 41-44 Hz. It SHALL NOT use the sensor library's automatic offset calibration, because that assumes a level module and would erase the tilt of the dash on which the module is mounted. The orientation assumed is X = front of the car, Y = left, Z = up.

#### Scenario: Ranges
- **WHEN** the device has booted
- **THEN** the gyroscope range is ±500 °/s and the accelerometer range is ±2 g

### Requirement: Data line
Once started, the device SHALL send one data line every 10 ms (100 per second): `#D;t_ms;pitch;roll;ax_g;ay_g;az_g;gx_dps;gy_dps;gz_dps;temp_c;`. `t_ms` SHALL be the milliseconds since boot. `pitch` and `roll` SHALL be in degrees, already minus the zero, with 2 decimals. `ax_g`, `ay_g` and `az_g` SHALL be in g with 3 decimals. `gx_dps`, `gy_dps` and `gz_dps` SHALL be in °/s with the gyroscope bias removed and 2 decimals. `temp_c` SHALL be the sensor temperature in °C with 1 decimal. The values SHALL be exactly ten, in that order. No data line SHALL be sent while a gyroscope calibration runs.

#### Scenario: Line shape
- **WHEN** the device is streaming
- **THEN** each line has the tag `#D` and exactly ten numeric values in the order above

#### Scenario: Rate
- **WHEN** the device is streaming and no command is running
- **THEN** it sends 100 data lines per second

#### Scenario: Time since boot
- **WHEN** two consecutive data lines are sent
- **THEN** the second `t_ms` is not lower than the first

### Requirement: Angle estimation
The pitch SHALL be positive with the nose down and the roll SHALL be positive with the right side down. The accelerometer angles SHALL be `pitch = atan2(-ax, sqrt(ay² + az²))` and `roll = atan2(ay, az)`, in degrees. At every sample the device SHALL integrate the gyroscope (`pitch += gy · dt`, `roll += gx · dt`) and SHALL then correct each angle with the accelerometer angle through a complementary filter that weighs the integrated angle at 0.98 and the accelerometer angle at 0.02, but only while the magnitude of the acceleration is within 0.15 g of 1 g (so braking, cornering and accelerating hard do not bend the angles).

#### Scenario: Nose down
- **WHEN** the module is still and the front of the car points down by 3 degrees
- **THEN** the pitch settles at +3 (before the zero)

#### Scenario: Right side down
- **WHEN** the module is still and the right side of the car is down by 2 degrees
- **THEN** the roll settles at +2 (before the zero)

#### Scenario: Hard braking
- **WHEN** the magnitude of the acceleration is 1.3 g
- **THEN** the accelerometer does not correct the angles in that sample

### Requirement: Command input
The device SHALL read commands from the serial port: a command is a line ended by `\n`; `\r` SHALL be ignored; the letters SHALL be compared after conversion to uppercase; a line SHALL hold at most 15 characters, and a longer line SHALL be discarded up to its `\n` with no reply. Commands are read between data lines, so a command is answered within one sample period (10 ms) when the device is streaming. The commands are `#Z` (set the zero), `#R` (remove the zero) and `#C` (recalibrate the gyroscope). Any other line, including an empty one, SHALL be answered with `#M;COMANDO_DESCONHECIDO;`.

#### Scenario: Lowercase accepted
- **WHEN** the device receives `#z\n`
- **THEN** it behaves as for `#Z`

#### Scenario: Carriage return
- **WHEN** the device receives `#Z\r\n`
- **THEN** it behaves as for `#Z`

#### Scenario: Unknown command
- **WHEN** the device receives `#X\n`
- **THEN** it sends `#M;COMANDO_DESCONHECIDO;`

#### Scenario: Line too long
- **WHEN** the device receives a line of 40 characters
- **THEN** it sends no reply and the next command is read normally

### Requirement: Command replies
Every known command SHALL be answered by a line of the form `#<CMD>;<STATUS>;`, where `<CMD>` is the command received (`#Z`, `#R` or `#C`). The reply SHALL be sent after the command took effect, except for the slow `#C`, whose first reply is sent before it starts. The replies are: `#Z;OK;` for `#Z`; `#R;OK;` for `#R`; and `#C;CALIBRANDO;` followed, when the calibration ends, by `#C;OK;` for `#C`. A command SHALL get exactly one reply per phase and the reply SHALL NOT depend on the zero or on any earlier command.

#### Scenario: Zero acknowledged
- **WHEN** the device receives `#Z`
- **THEN** it sends `#Z;OK;`

#### Scenario: Zero removal acknowledged
- **WHEN** the device receives `#R`
- **THEN** it sends `#R;OK;`

#### Scenario: Slow command
- **WHEN** the device receives `#C`
- **THEN** it sends `#C;CALIBRANDO;` before it stops streaming and `#C;OK;` after the calibration ended

#### Scenario: Same reply every time
- **WHEN** `#Z` is received twice in a row
- **THEN** each one is answered with `#Z;OK;`

### Requirement: Zero
On `#Z` the device SHALL store the current filtered pitch and roll as the zero, and from the next data line SHALL send the angles minus that zero. On `#R` it SHALL clear the zero (both offsets 0). The zero SHALL be kept until `#R` or a reset; a gyroscope recalibration SHALL NOT clear it (the dashboard still treats the zero as lost after a calibration, see `gyro-connection`). The zero SHALL be applied only to the `pitch` and `roll` of the data line.

#### Scenario: Zero applied
- **WHEN** the filtered pitch is 4.0 and the device receives `#Z`
- **THEN** the next data line has a pitch close to 0

#### Scenario: Zero removed
- **WHEN** the device was zeroed at pitch 4.0 and receives `#R` while the filtered pitch is 4.0
- **THEN** the next data line has a pitch close to 4.0

#### Scenario: Zero kept through a calibration
- **WHEN** the device was zeroed and runs `#C`
- **THEN** the zero offsets are unchanged after `#C;OK;`

#### Scenario: Lost on reset
- **WHEN** the device was zeroed and is reset
- **THEN** the zero is empty after the boot

### Requirement: Gyroscope calibration
The calibration (at boot and on `#C`) SHALL send `#C;CALIBRANDO;`, average 500 gyroscope readings taken about 3 ms apart (about 1.5 s) as the bias of the three axes, set the pitch and roll directly from the accelerometer, and send `#C;OK;`. The device SHALL send no data line while it runs. When it ends the streaming clock SHALL restart so that the first sample after it does not integrate the time of the calibration. The car must be stopped while it runs. At boot the two lines are sent without a command and have the same meaning as the replies.

#### Scenario: Pause in the stream
- **WHEN** `#C` is received
- **THEN** no data line is sent between `#C;CALIBRANDO;` and `#C;OK;`

#### Scenario: Duration
- **WHEN** `#C` is received
- **THEN** `#C;OK;` follows within 10 seconds (about 1.5 s)

#### Scenario: Bias removed
- **WHEN** the module is still after a calibration
- **THEN** the `gx_dps`, `gy_dps` and `gz_dps` of the data lines are close to 0

#### Scenario: No jump after the calibration
- **WHEN** the calibration ends
- **THEN** the first sample integrates the gyroscope over one sample period, not over the calibration time

### Requirement: Messages
The `#M` line SHALL carry one text item: `#M;<TEXT>;`. It SHALL be used only for information that is not a command reply: the boot hint, the sensor failure and the unknown command. No `#M` text SHALL be required for the dashboard to know the state of the zero or of a calibration.

#### Scenario: Message shape
- **WHEN** the device sends a message
- **THEN** the line is `#M;` followed by one text and `;`

### Requirement: Firmware matches the dashboard's protocol
The tags, command names, statuses and the order of the fields of the data and header lines in the firmware SHALL be the ones the dashboard uses, so that the two sides never diverge.

#### Scenario: Contract check
- **WHEN** the automated contract check reads the firmware source
- **THEN** it finds each command, each status and the header line the dashboard uses, and no `#M` text that the dashboard compares
