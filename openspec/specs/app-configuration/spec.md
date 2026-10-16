# app-configuration Specification

## Purpose

Defines how the dashboard loads its runtime settings from a JSON file, which sections and keys exist, and which defaults apply when a key or the whole file is missing.

## Requirements

### Requirement: Configuration file location
The system SHALL read its settings once at startup from the file named by the `MI_DASHBOARD_CONFIG_FILE` environment variable, or from `config.json` in the current working directory when the variable is not set. If the file does not exist, the system SHALL start with the built-in defaults for every setting.

#### Scenario: Default file name
- **WHEN** the app starts without `MI_DASHBOARD_CONFIG_FILE` and `config.json` exists in the working directory
- **THEN** the settings are loaded from that `config.json`

#### Scenario: Environment override
- **WHEN** `MI_DASHBOARD_CONFIG_FILE` points to an existing JSON file
- **THEN** the settings are loaded from that file instead of `config.json`

#### Scenario: File absent
- **WHEN** the resolved configuration file does not exist
- **THEN** the app starts using the built-in defaults for all settings

### Requirement: Per-key defaults
Each section and key SHALL be optional. A missing section or key SHALL take its built-in default independently of the other keys.

#### Scenario: Partial section
- **WHEN** `connection` contains only `port`
- **THEN** `baudrate` is `115200` and `mock` is empty

### Requirement: Supported settings
The system SHALL support the following settings and defaults.

| Key | Meaning | Default |
|---|---|---|
| `connection.port` | Serial port name | empty |
| `connection.baudrate` | Serial baud rate | `115200` |
| `connection.mock` | Path of a CSV file to replay; when non-empty the mock source replaces the serial port | empty (use serial) |
| `connection.mock_skip_lines` | Number of data lines (after the header) the mock source skips on its first pass | `0` |
| `alarm.sound` | Audio file played while any alarm is firing | `alarm.wav` |
| `datalog.path` | Directory where CSV logs are created | not a usable directory (see design.md, Known issues) |
| `datalog.mark_sound` | Audio played when the user marks an event | `alarm.wav` |
| `dashboard.grid` | 2-D list of signal names for the numeric grid | 2 rows: `RPM, VSS, MAP, BOOST, CLT, IAT, POWER` / `LAMBDA, LAMBDA_TARGET, FUEL_TRIM, BOOST_TARGET, INJ_UTIL, IGN, TORQUE` |
| `dashboard.graph` | List of graph groups; each group is a list of signal names sharing one plot | 2 groups: `RPM, MAP` / `LAMBDA, LAMBDA_TARGET, FUEL_TRIM` |
| `dashboard.graph_x_size` | Number of samples kept per graph series | `150` |
| `ve_calibration.ve_sound` | Audio played after VE rows are written to the ECU | `alarm.wav` |
| `ve_calibration.closed_sound` | Audio played when the close-loop key is pressed | `alarm.wav` |
| `ve_calibration.open_sound` | Audio played when the open-loop key is pressed | `alarm.wav` |
| `ignition_tuning.rpm_min` | Lower RPM bound (inclusive) of the analysed band | `2900` |
| `ignition_tuning.rpm_max` | Upper RPM bound (inclusive) of the analysed band | `3100` |
| `ignition_tuning.gears` | List of gears in which samples are analysed | `[5]` |
| `ignition_tuning.max_map_kpa` | Highest MAP axis value (inclusive) of the rows changed by the advance offset | `70` |
| `ignition_tuning.max_ignition` | Highest raw ignition value (degrees) a cell can reach | `50` |
| `ignition_tuning.settle_seconds` | Seconds to discard samples after a write or a resume | `5` |
| `ignition_tuning.min_scenario_seconds` | Analysed seconds a scenario needs to be compared | `20` |
| `ignition_tuning.write_sound` | Audio played after ignition rows are written to the ECU | `alarm.wav` |
| `ignition_tuning.ready_sound` | Audio played when the current scenario has enough analysed time | `alarm.wav` |
| `ignition_tuning.pause_sound` | Audio played when the analysis is paused | `alarm.wav` |
| `ignition_tuning.resume_sound` | Audio played when the analysis is resumed | `alarm.wav` |
| `ignition_tuning.discard_sound` | Audio played when the worst scenario is discarded | `alarm.wav` |

#### Scenario: Mock selected by configuration
- **WHEN** `connection.mock` is a non-empty path
- **THEN** the app replays that file instead of opening a serial port

#### Scenario: Signal names in layout settings
- **WHEN** `dashboard.grid` or `dashboard.graph` contain signal names
- **THEN** each name refers to a signal identifier from the signal catalog (for example `RPM`, `VSS`, `LAMBDA_TARGET`)

#### Scenario: Skip configured
- **WHEN** `connection.mock_skip_lines` is `500`
- **THEN** the mock source starts emitting from the 501st data line of the file

#### Scenario: Mark sound configured
- **WHEN** `datalog.mark_sound` names an audio file
- **THEN** that file is played when an event is marked

#### Scenario: Ignition tuning defaults
- **WHEN** the configuration has no `ignition_tuning` section
- **THEN** the band is 2900 to 3100 RPM, the analysed gears are `[5]`, the MAP limit is 70, the ceiling is 50, settling is 5 seconds and the minimum scenario time is 20 seconds

#### Scenario: Ignition tuning band configured
- **WHEN** `ignition_tuning.rpm_min` is `3400` and `ignition_tuning.rpm_max` is `3600`
- **THEN** only samples with RPM from 3400 to 3600 are analysed

#### Scenario: Ignition tuning gears configured
- **WHEN** `ignition_tuning.gears` is `[4, 5]`
- **THEN** samples in 4th and in 5th gear are analysed

#### Scenario: Previous gear key not read
- **WHEN** the configuration has `ignition_tuning.gear` set to `4` and no `ignition_tuning.gears`
- **THEN** the analysed gears are `[5]`

### Requirement: Fixed signal definitions
Signal indices, display names, units, graph ranges, colors and alarm limits SHALL NOT be configurable through the configuration file; they are fixed by the signal catalog.

#### Scenario: Attempt to override limits
- **WHEN** the configuration file contains alarm limits for a signal
- **THEN** they are ignored

### Requirement: Inclinometer and tilt settings
The system SHALL support these settings in addition to those in "Supported settings".

| Key | Meaning | Default |
|---|---|---|
| `gyro.port` | Serial port name of the inclinometer; empty means there is no inclinometer | empty |
| `ignition_tuning.max_tilt_deg` | Highest absolute pitch (degrees, inclusive) at which the ignition analysis samples | `3` |

There SHALL be no baud rate setting for the inclinometer: the link is fixed at 115200 baud (see `gyro-connection`). A `max_tilt_deg` that is not a number, or is not greater than 0, SHALL take the default.

#### Scenario: Defaults without the section
- **WHEN** the configuration has no `gyro` section and no `max_tilt_deg`
- **THEN** `gyro.port` is empty and `max_tilt_deg` is 3

#### Scenario: Port configured
- **WHEN** `gyro.port` is `COM7`
- **THEN** the inclinometer connection uses `COM7`

#### Scenario: Invalid limit
- **WHEN** `ignition_tuning.max_tilt_deg` is `"abc"`, `0` or `-2`
- **THEN** the limit is 3

### Requirement: Saving the configuration
The system SHALL be able to save a changed setting to the same file it was loaded from (the file named by `MI_DASHBOARD_CONFIG_FILE`, or `config.json` in the working directory). Saving SHALL read the file again at that moment, change only the value of the edited key inside its section (creating the section or the file when absent) and write the whole content back, so keys the app does not know and keys edited by hand since the app started are kept. The file SHALL always be written formatted as JSON indented with 2 spaces, UTF-8 with non-ASCII characters unescaped, keys in their existing order (a new key or section is appended) and a final line break. The write SHALL go to a temporary file in the same directory that then replaces the configuration file, so an interrupted write never leaves a half-written file. Settings that were not edited SHALL NOT be added to the file. When the existing file cannot be read or is not a JSON object, saving SHALL fail, SHALL NOT overwrite the file and SHALL report the failure to the caller. A saved value SHALL also be the value used by the running app, whether or not saving succeeded.

#### Scenario: Value saved in place
- **WHEN** `ignition_tuning.settle_seconds` is saved as 6 and the file has other keys in that section
- **THEN** the file holds `"settle_seconds": 6` and every other key unchanged

#### Scenario: Always indented
- **WHEN** any setting is saved to a file that was written on a single line
- **THEN** the file afterwards is indented with 2 spaces on separate lines and ends with a line break

#### Scenario: Unknown keys kept
- **WHEN** the file has a key the app does not know and another setting is saved
- **THEN** the unknown key is still in the file with its value

#### Scenario: Edited by hand meanwhile
- **WHEN** the file was edited by hand after the app started and a different setting is saved
- **THEN** the hand edit is still in the file

#### Scenario: Section created
- **WHEN** `gyro.port` is saved and the file has no `gyro` section
- **THEN** the file gets a `gyro` section with `port`

#### Scenario: File created
- **WHEN** the file does not exist and a setting is saved
- **THEN** the file is created with only that setting

#### Scenario: Defaults not copied
- **WHEN** one setting is saved
- **THEN** no other setting that was absent from the file is added to it

#### Scenario: Non-ASCII text
- **WHEN** the file has a value with accents and another setting is saved
- **THEN** the accents are written as they are, not as `\u` escapes

#### Scenario: Invalid file
- **WHEN** the file holds text that is not valid JSON and a setting is saved
- **THEN** the file is left untouched, the failure is reported and the running app uses the new value

#### Scenario: Atomic replace
- **WHEN** a setting is saved
- **THEN** no temporary file remains in the directory afterwards

#### Scenario: Environment override
- **WHEN** the app was loaded from the file named by `MI_DASHBOARD_CONFIG_FILE` and a setting is saved
- **THEN** that file is the one written

### Requirement: Every setting is on the Settings screen
Every setting of the configuration file SHALL be editable on the Settings screen (see `settings-screen`). A new setting SHALL be added together with its Settings screen row in the same change. The settings that exist today and are not yet on the screen are the exceptions below, and the list SHALL shrink as they move to the screen and SHALL NOT grow: `connection.port`, `connection.baudrate`, `connection.mock`, `connection.mock_skip_lines`, `alarm.sound`, `datalog.path`, `datalog.mark_sound`, `dashboard.grid`, `dashboard.graph`, `dashboard.graph_x_size`, `ve_calibration.ve_sound`, `ve_calibration.closed_sound`, `ve_calibration.open_sound`, `ignition_tuning.gears`, `ignition_tuning.max_map_kpa`, `ignition_tuning.max_ignition`, `ignition_tuning.write_sound`, `ignition_tuning.ready_sound`, `ignition_tuning.pause_sound`, `ignition_tuning.resume_sound` and `ignition_tuning.discard_sound`.

#### Scenario: Setting with a row
- **WHEN** the settings of the configuration are compared with the rows of the Settings screen and the exceptions
- **THEN** `gyro.port`, `ignition_tuning.max_tilt_deg`, `ignition_tuning.rpm_min`, `ignition_tuning.rpm_max`, `ignition_tuning.settle_seconds` and `ignition_tuning.min_scenario_seconds` have a row

#### Scenario: Setting without a row
- **WHEN** a setting exists in the configuration that has no Settings screen row and is not in the list of exceptions
- **THEN** the comparison fails, so a new setting cannot be added without its row
