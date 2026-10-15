## Why

Ignition tuning compares the injection time of several advance offsets at the same cruising speed. A slope changes the load the engine needs, so samples taken uphill or downhill are not comparable with samples taken on the flat. An inclinometer (MPU-6500 on an Arduino, serial 115200 8N1, 100 Hz) can tell the dashboard when the car is not level, so the analysis stops sampling until the car is level again and the setting has settled.

The app also needs a place to configure this device from the driver's seat. The configuration file today can only be edited by hand, so this change starts a **Settings** screen that edits `config.json`, and makes it a project rule that every setting is on that screen.

## What Changes

- **Inclinometer connection** (new `app/gyro/`): optional serial device on `gyro.port`. The app opens it by itself, retries every 2 s while it is configured but absent, and reads the `#D;…;` data lines (pitch, roll, accelerations, rotation, temperature), the `#H;…;` header and the `#M;…;` messages. It can send `#Z` (set zero) and `#C` (recalibrate the gyroscope); `#R` (remove the zero) is not used by the app. The app stores no angle offset: the device applies the zero. The app only tracks whether the device is zeroed, from the device's own `#M;Zero definido;` answer.
- **Manual zero only.** After the app starts, after the port is (re)opened, after the device restarts (`#H` or `t_ms` going back) and after a recalibration, the inclination is **not used** until the user zeroes it (key `G` on the Ignition tuning screen, or the Settings screen).
- **Ignition analysis requires the inclinometer when it is configured.** With a port configured, a telemetry set is a sample only while the pitch is usable (connected, signal present, not calibrating, zeroed) and `|pitch| <= ignition_tuning.max_tilt_deg`. New statuses `AGUARDANDO SENSOR` and `INCLINADO`. When the sensor becomes usable and level again, samples are discarded for `ignition_tuning.settle_seconds`. With no port configured nothing changes.
- **Ignition tuning screen**: a box on top shows the inclination (`+1.4° ↓`, `sem zero (G)`, `sem sinal`…), and key **G** sends the zero command.
- **Settings screen** (new, key **F12**, Home entry `Configurações`): gyro port (choice, including `Nenhuma`), connect / disconnect, zero, recalibrate gyroscope, live pitch / roll / temperature and the last device message, and the settings `ignition_tuning.max_tilt_deg`, `rpm_min`, `rpm_max`, `settle_seconds`, `min_scenario_seconds`.
- **The app now writes `config.json`.** Every change on the Settings screen is saved immediately: the current file is read again, only the edited key is changed, and the whole file is written back indented (2 spaces) through a temporary file. New settings: `gyro.port` (default empty) and `ignition_tuning.max_tilt_deg` (default `3`). There is no `gyro.baudrate`: the protocol fixes 115200.
- **Project rule:** every setting must be editable on the Settings screen. Settings that exist today and are not on the screen yet are listed as an explicit backlog, and a test fails when a setting is neither on the screen nor in that backlog.
- **Rename:** the screen called `Opções` is shown as **ECU** (Home entry, title). Its internal name `options` and the capability `options-screen` stay.
- The Home menu gets a fifth entry, `Configurações`, and F12 becomes a sixth global shortcut.

## Capabilities

### New Capabilities
- `gyro-connection`: the optional inclinometer: serial link, line parser, device states, zero / recalibrate commands, what counts as a usable pitch.
- `settings-screen`: the Settings screen: rows, keyboard behaviour, gyro actions, ignition tuning settings, status messages, saving.

### Modified Capabilities
- `ignition-analysis`: inclination condition, settling when the inclination becomes usable and level, band change discards scenarios.
- `ignition-tuning-screen`: footer hint, new statuses in the top bar, inclination box, key G.
- `screen-navigation`: sixth screen `settings`, Home menu with `ECU` and `Configurações`, ESC from Settings, F12.
- `options-screen`: the title reads `ECU`.
- `app-configuration`: `gyro.port` and `ignition_tuning.max_tilt_deg`, saving to the file, rule that every setting is on the Settings screen.
- `app-lifecycle`: the inclinometer connection is stopped on shutdown.

## Impact

- Code: new `app/gyro/` (parser and state, serial connection thread, registry), new `app/ui/settings/` (screen), `app/config.py` (new keys, `save`), `app/ui/ignition_tuning/analysis.py` and `screen.py`, `app/ui/home/screen.py`, `app/ui/window.py` (register screen, F12, rename), `app/ui/options/screen.py` (title), `app/lifecycle.py`, `main.py` (create the gyro connection, wire it).
- Tests: new `tests/test_gyro_connection.py` and `tests/test_settings_screen.py`; updated `tests/test_app_configuration.py`, `tests/test_ignition_analysis.py`, `tests/test_ignition_tuning_screen.py`, `tests/test_screen_navigation.py`, `tests/test_window.py`, `tests/test_options_screen.py`, `tests/test_lifecycle.py`.
- Docs and project rules: `CLAUDE.md` (code layout, capability list, configuration rule), `openspec/config.yaml` (rule for specs and tasks), `README.md`.
- No new dependency (`pyserial` already provides `serial.tools.list_ports`).
- **Order dependency:** `ecu-phase-option` is already archived. This change is written against the specs as they will be once the finished `ignition-multi-gear` is archived too (it modifies requirements that change adds), so archive `ignition-multi-gear` first, or this change's blocks would be applied on top of the older text and `openspec archive` would drop its updates.
