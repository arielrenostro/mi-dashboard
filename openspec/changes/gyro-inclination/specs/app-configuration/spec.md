## ADDED Requirements

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
