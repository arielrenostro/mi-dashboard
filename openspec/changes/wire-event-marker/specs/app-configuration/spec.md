## MODIFIED Requirements

### Requirement: Supported settings
The system SHALL support the following settings and defaults.

| Key | Meaning | Default |
|---|---|---|
| `connection.port` | Serial port name | empty |
| `connection.baudrate` | Serial baud rate | `115200` |
| `connection.mock` | Path of a CSV file to replay; when non-empty the mock source replaces the serial port | empty (use serial) |
| `alarm.sound` | Audio file played while any alarm is firing | `alarm.wav` |
| `datalog.path` | Directory where CSV logs are created | not a usable directory (see design.md, Known issues) |
| `datalog.mark_sound` | Audio played when the user marks an event | `alarm.wav` |
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

#### Scenario: Mark sound configured
- **WHEN** `datalog.mark_sound` names an audio file
- **THEN** that file is played when an event is marked
