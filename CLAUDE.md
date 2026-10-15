# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Real-time automotive ECU telemetry dashboard for the Master Injection ECU. It reads data over a Bluetooth serial COM port (Windows), parses semicolon-delimited frames, displays live signal values and graphs, plays audio alarms, logs raw data to CSV, and supports keyboard-driven screen navigation, VE map calibration and on-road ignition tuning.

## Running the app

```
.venv\Scripts\python main.py
```

No build step. Dependencies:

```
pip install -r requirements.txt       # pyserial, pyqt6, pyqtgraph
pip install -r requirements-dev.txt   # adds pytest (for the tests)
```

## Testing (mandatory)

**Every feature, behavior change and bug fix ships with unit tests, in the same change.** Code without tests is not done: do not mark a task complete, archive a change, or call work finished until the new tests exist and the whole suite passes.

```
.venv\Scripts\python -m pytest         # Windows
.venv-wsl/bin/python -m pytest         # WSL (see "WSL test environment" below)
```

Rules:
- Tests live in `tests/`, one file per capability (`tests/test_<capability>.py`). Name tests after the spec scenario they cover and cite the requirement or scenario in the docstring, so every scenario in `openspec/specs/` has at least one test. When a spec changes, change its tests in the same OpenSpec change.
- Bug fixes start with a regression test that fails before the fix.
- Test the spec, not known defects: do not assert behavior listed under "Known issues" in the archived baseline design.
- Tests must run without hardware, a display, audio devices or the developer's `config.json`. Use fakes (for example `FakeSerial` in `tests/test_ecu_connection_serial.py`), real Qt objects in offscreen mode (set up by `tests/conftest.py`), and `tests/helpers.py` (`SAMPLE_FRAME`, `frame_with`, `parsed`, `key_press`). The `vehicle_state` singleton is reset around every test; reset other module singletons (`ve_map_state`) in the fixture that uses them.
- Test through real code paths where possible (feed a frame through `SignalProcessor`, publish rows through `vehicle_state`) instead of poking private state.
- If something truly cannot be unit tested (real hardware, real audio output), say so explicitly in the task and state how it was verified manually.
- After editing a source file twice within the same second, stale `.pyc` files can mask results; clear `__pycache__` if a result looks impossible.

### WSL test environment

The pinned `requirements.txt` needs Python 3.11+, so in WSL (Python 3.10) use a separate venv with unpinned packages:

```
python3 -m venv .venv-wsl
.venv-wsl/bin/pip install PyQt6 pyqtgraph numpy pyserial pytest
```

## Specifications (OpenSpec)

`openspec/specs/` is the source of truth for what the system does. There is one folder per capability (`ecu-connection`, `ecu-protocol`, `signal-model`, `vehicle-state`, `alarms`, `dashboard`, `screen-navigation`, `ve-map-model`, `ve-calibration-screen`, `ve-write`, `datalog`, `lambda-loop-control`, `ignition-map-model`, `ignition-analysis`, `ignition-tuning-screen`, `options-screen`, `phase-write`, `gyro-connection`, `settings-screen`, `app-configuration`, `app-lifecycle`). Read the relevant spec before changing behavior.

- Behavior changes go through an OpenSpec change (`/opsx:propose <name>`, then `/opsx:apply`, then `/opsx:archive`), so the specs stay in sync with the code. Each change's `tasks.md` must include its unit-test tasks (see Testing).
- Known defects and the rationale behind the baseline are recorded in `openspec/changes/archive/*-baseline-existing-system/design.md` ("Known issues").
- When code and specs disagree, say so instead of silently picking one.

## Configuration (`config.json`)

Settings are loaded from `config.json` in the working directory, or from the file named by the `MI_DASHBOARD_CONFIG_FILE` environment variable. If the file is absent, built-in defaults apply. Sections: `connection`, `alarm`, `datalog`, `dashboard`, `ve_calibration`, `ignition_tuning` (analysed gears are the list `ignition_tuning.gears`), `gyro` (the optional inclinometer port). Keys and defaults are specified in `openspec/specs/app-configuration/spec.md`.

**The app writes `config.json`.** The Settings screen (F12) saves every change at once with `AppConfig.set_value(section, key, value)`: it re-reads the file, changes only that key and writes the whole file back indented (2 spaces) through a temporary file. Never write the file any other way, and in tests never let a save reach a real file (`tests/conftest.py` already points the singleton at a temporary path).

**Rule: every setting must be editable on the Settings screen.** A new setting ships together with its row in `app/ui/settings/screen.py` (a `NumberRow`, or a choice / action row), its spec scenario and its test, in the same change. Settings that predate the rule and are not on the screen yet are listed in `SETTINGS_BACKLOG` (same file); that list may only shrink, and `tests/test_app_configuration.py` fails when a setting is neither on the screen nor in the backlog.

All signal indices, limits, display formats and graph colors are intentionally hardcoded in `app/masterinjection/signal.py` — this is a personal script.

## Code layout

```
main.py                    wiring and Qt event loop
app/ecu_connection/        serial / mock sources, thread wrapper, registry
app/masterinjection/       Signal catalog, SignalProcessor, protocol enums
app/state/                 VehicleState (shared, RLock-protected) and change events
app/alarm/                 AlarmProcessor (limit checks + alarm sound)
app/log_writer/            CSV LogWriter (own thread)
app/ui/                    AppWindow, Home, Dashboard, VE calibration, ignition tuning (per-gear analysis,
                           IgnitionResultsLog CSV snapshot in datalog.path), SignalCard
app/ui/options/            OptionsScreen (shown as "ECU": engine phase) and PhaseWriteController (read-modify-write of #X02, never #D04)
app/ui/settings/           SettingsScreen (F12): edits config.json settings, connects / zeroes / recalibrates the inclinometer
app/gyro/                  optional inclinometer: protocol parser, GyroState (zero flag, status), GyroConnection (serial thread)
app/ui/common/             RowWriteController (debounced row-by-row map write, shared by VE and ignition)
app/config.py              config.json loader and saver
```

All cross-thread communication goes through `pyqtSignal` / `@Slot`; the UI is never touched from background threads, and `QMediaPlayer` calls run on the main thread.

## Adding or modifying signals

1. Add/edit an entry in the `Signal` enum in `app/masterinjection/signal.py` (calculated signals use `"calculated": True` and a `"value"` lambda; they must come after their dependencies in the enum).
2. Add it to `config.json` under `dashboard.grid` and/or `dashboard.graph` (use the enum member name as the string key).
3. Update `openspec/specs/signal-model/spec.md` through an OpenSpec change.

## Sending commands to the ECU

Call `get_ecu_connection().send_command(cmd, args)` from any thread — it is queued internally and written after the next complete frame. Add new commands to `EcuCommand` in `app/masterinjection/protocol.py` and to the `ecu-protocol` spec.
