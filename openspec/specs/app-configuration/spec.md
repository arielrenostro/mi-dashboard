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
| `ignition_tuning.gear` | Gear in which samples are analysed | `5` |
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
- **THEN** the band is 2900 to 3100 RPM, the gear is 5, the MAP limit is 70, the ceiling is 50, settling is 5 seconds and the minimum scenario time is 20 seconds

#### Scenario: Ignition tuning band configured
- **WHEN** `ignition_tuning.rpm_min` is `3400` and `ignition_tuning.rpm_max` is `3600`
- **THEN** only samples with RPM from 3400 to 3600 are analysed

### Requirement: Fixed signal definitions
Signal indices, display names, units, graph ranges, colors and alarm limits SHALL NOT be configurable through the configuration file; they are fixed by the signal catalog.

#### Scenario: Attempt to override limits
- **WHEN** the configuration file contains alarm limits for a signal
- **THEN** they are ignored
