## Purpose

Defines how the dashboard loads its runtime settings from a JSON file, which sections and keys exist, and which defaults apply when a key or the whole file is missing.

## ADDED Requirements

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
| `alarm.sound` | Audio file played while any alarm is firing | `alarm.wav` |
| `datalog.path` | Directory where CSV logs are created | not a usable directory (see design.md, Known issues) |
| `dashboard.grid` | 2-D list of signal names for the numeric grid | 2 rows: `RPM, VSS, MAP, BOOST, CLT, IAT, POWER` / `LAMBDA, LAMBDA_TARGET, FUEL_TRIM, BOOST_TARGET, INJ_UTIL, IGN, TORQUE` |
| `dashboard.graph` | List of graph groups; each group is a list of signal names sharing one plot | 2 groups: `RPM, MAP` / `LAMBDA, LAMBDA_TARGET, FUEL_TRIM` |
| `dashboard.graph_x_size` | Number of samples kept per graph series | `150` |
| `ve_calibration.ve_sound` | Audio played after VE rows are written to the ECU | `alarm.wav` |
| `ve_calibration.closed_sound` | Audio played when the close-loop key is pressed | `alarm.wav` |
| `ve_calibration.open_sound` | Audio played when the open-loop key is pressed | `alarm.wav` |

#### Scenario: Mock selected by configuration
- **WHEN** `connection.mock` is a non-empty path
- **THEN** the app replays that file instead of opening a serial port

#### Scenario: Signal names in layout settings
- **WHEN** `dashboard.grid` or `dashboard.graph` contain signal names
- **THEN** each name refers to a signal identifier from the signal catalog (for example `RPM`, `VSS`, `LAMBDA_TARGET`)

### Requirement: Fixed signal definitions
Signal indices, display names, units, graph ranges, colors and alarm limits SHALL NOT be configurable through the configuration file; they are fixed by the signal catalog.

#### Scenario: Attempt to override limits
- **WHEN** the configuration file contains alarm limits for a signal
- **THEN** they are ignored
