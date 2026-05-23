# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Real-time automotive ECU telemetry dashboard for the Master Injection ECU. It reads data over a Bluetooth serial COM port (Windows), parses semicolon-delimited frames, displays live signal values and graphs, plays audio alarms, logs raw data to CSV, and supports keyboard-driven screen navigation and VE map calibration.

## Running the app

```
.venv\Scripts\python main.py
```

No build step. No test suite. Dependencies:

```
pip install -r requirements.txt   # pyserial, pyqt6, pyqtgraph
```

## Configuration (`config.json`)

Settings are loaded from `config.json` in the project root. If the file is absent, built-in defaults apply. The `LOG_FILE` path is still hardcoded at the top of `main.py`.

```json
{
  "connection": { "port": "COM1", "baudrate": 115200, "mock": "" },
  "alarm":      { "sound": "alarm.wav" },
  "dashboard":  {
    "grid": [["RPM", "VSS", "MAP", "BOOST", "CLT", "IAT", "POWER"],
             ["LAMBDA", "LAMBDA_TARGET", "FUEL_TRIM", "BOOST_TARGET", "INJ_UTIL", "IGN", "TORQUE"]],
    "graph": [["RPM", "MAP"], ["LAMBDA", "LAMBDA_TARGET", "FUEL_TRIM"]],
    "graph_x_size": 150
  },
  "ve_calibration": {
    "ve_sound": "alarm.wav",
    "closed_sound": "alarm.wav",
    "open_sound": "alarm.wav"
  }
}
```

| Key | Purpose |
|---|---|
| `connection.port` | Windows COM port (e.g. `"COM5"`) |
| `connection.baudrate` | Serial baud rate |
| `connection.mock` | If non-empty, uses `EcuConnectionMock` replaying this CSV file |
| `alarm.sound` | `.wav` played while any signal is outside its limits |
| `dashboard.grid` | 2-D list of signal names for the numeric display grid |
| `dashboard.graph` | List of row groups; each group shares one plot |
| `dashboard.graph_x_size` | Number of samples kept per graph buffer |
| `ve_calibration.*_sound` | `.wav` files for VE edit, loop-close, and loop-open feedback |

All signal indices, limits, and graph colors are intentionally hardcoded in `app/masterinjection/signal.py` — this is a personal script.

## Architecture

### Data flow

```
EcuConnectionSerial / EcuConnectionMock  (via EcuConnectionThread : QThread)
    │  emitter(str)  — raw semicolon-joined "#D01;...;#D02;..." line
    ├──► SignalProcessor.process_line()
    │         │  emitter(dict)  — {Signal: ParsedSignal}
    │         ├──► DashboardScreen.on_signal_received()    (UI update)
    │         ├──► AlarmProcessor.process_signals()        (alarm check)
    │         ├──► VehicleState.update()                   (global state snapshot)
    │         ├──► LambdaLoopStateProcessor.on_signal_received() (effective loop state)
    │         └──► VeCalibrationScreen.process_signals()   (top bar update)
    └──► LogWriter.write()                                 (CSV append)

AlarmProcessor.emitter(Signal) ──► [pending] DashboardScreen.fire_field_alarm()

AppWindow  dispatches keyPressEvent / keyReleaseEvent  ──► current Screen
    VeCalibrationScreen.keyPressEvent():  ↑/↓ → adjust VE,  R → reset VE
    HomeScreen.keyPressEvent():           ↑/↓ → nav,  Enter → select screen
    AppWindow.keyPressEvent():            ESC → go_home()

[pending] AppWindow.key_event(int) ──► EventMarker.handle_key()
                                   └──► KeyHoldDetector.on_key_pressed()
[pending] AppWindow.key_released(int) ──► KeyHoldDetector.on_key_released()
              └─ (after 2 s hold) triggered ──► LambdaToggle.handle_trigger()
                                                    ├─ command_requested ──► EcuConnection.send_command()
                                                    └─ command_requested ──► LambdaLoopStateProcessor.on_command_received()
```

All cross-thread communication goes through `pyqtSignal` / `@Slot`. The UI is never touched from background threads. `QMediaPlayer` calls are always dispatched to the main thread via `Qt.ConnectionType.QueuedConnection`.

### Modules

**`app/ecu_connection/`** — ECU communication
- `ecu_connection.py`: Abstract `EcuConnection` base class. Defines `send_command(cmd, args)`, `run()`, `start()`, `stop()`, `is_connected()`.
- `serial.py`: `EcuConnectionSerial` — connects to the COM port, sends `#D50` (handshake) then `#D01` (start streaming). Buffers `#D01` and `#D02` lines and emits them joined as `"#D01...;#D02..."`. Reconnects after 3 consecutive empty reads. `send_command()` is thread-safe via an internal `queue.Queue`, drained after each complete frame.
- `mock_log.py`: `EcuConnectionMock` — replays a CSV log file, timing emissions based on embedded timestamps. `send_command()` is a no-op.
- `thread.py`: `EcuConnectionThread (QThread)` — wraps any `EcuConnection` and owns the `emitter(str)` pyqtSignal. Calls `ecu_connection.run()` in a loop.
- `__init__.py`: Module-level `register_ecu_connection()` / `get_ecu_connection()` / `get_ecu_connection_thread()` registry.

**`app/masterinjection/`** — Domain models
- `signal.py`: `Signal` enum — the single source of truth for every ECU signal. Each entry defines `index` (CSV column position in the combined frame), `converter` (raw→value), `for_label` (value→display string), `unit`, `min`/`max` (graph range), `color`, and `alarm` config. Signals with `calculated: True` (e.g. `POWER`, `TORQUE`) derive their value via a `"value"` lambda over already-parsed data. Order in the enum matters — calculated signals must come after all their dependencies.
- `signal_processor.py`: `SignalProcessor (QObject)` — splits the joined line on `;`, iterates all `Signal` enum members, applies converters, builds the `parsed_data` dict, emits it via `emitter(dict)`.
- `protocol.py`: `EcuCommand` / `EcuResponse` enums for the serial protocol. `EcuCommand` entries include `cmd` (the wire string) and `description`.

**`app/state/`** — Global vehicle state
- `state.py`: `VehicleState` with `threading.RLock`. Stores the latest signal snapshot (`update()` / `get()` / `get_all()`), alarm timestamps (`is_alarm_firing()` / `set_alarm()`), effective lambda loop state (`is_lambda_loop_closed()` / `set_lambda_loop_state()`), and ECU map data (`rpm_breakpoints`, `map_breakpoints`, `ve_map`). Emits `VehicleStateChangeEvent` on breakpoint/VE map updates. Module-level singleton `vehicle_state` imported everywhere.
- `processors/lambda_loop_state.py`: `LambdaLoopStateProcessor` — determines the effective lambda loop state, filtering transient open-loop during deceleration fuel cut. Rule: "closed" from ECU is always fact; "open" is only accepted when `PEDAL == 0 AND MAP ≤ 20 kPa` is false. `on_command_received()` updates `VehicleState` immediately when a toggle command is dispatched.
- `event.py`: `VehicleStateChangeEvent` + `EventType` enum for typed state-change notifications.
- `register.py`: helpers for the processor registry.

**`app/ui/`** — Qt UI
- `window.py`: `AppWindow (QWidget)` — full-screen window with a `QStackedWidget`. Self-registers all screens in `_register_screens()`. Routes `keyPressEvent`/`keyReleaseEvent` to the currently active screen. `show_screen(name)` calls `on_deactivated()` on the outgoing screen and `on_activated()` on the incoming one.
- `base/screen.py`: `Screen (QWidget)` — base class for all screens. Lifecycle hooks: `on_activated()`, `on_deactivated()` (no-ops by default).
- `home/screen.py`: `HomeScreen` — vertical menu (Dashboard, VE Calibration). `↑`/`↓` to navigate, `Enter` to open. Emits `screen_requested(str)`.
- `dashboard/screen.py`: `DashboardScreen` — full-screen numeric grid + graphs. Grid and graph layout taken from `config.json`. Graph data in `deque(maxlen=graph_x_size)`, refreshed every 100 ms via `QTimer`.
- `ve_calibration/screen.py`: `VeCalibrationScreen` — 16×16 VE map table + heatmap + top-bar signal cells. `↑`/`↓` edits VE; `R` resets. Emits `ve_adjustment_made` to trigger the write debounce.
- `ve_calibration/ve_map_state.py`: `VeMapState` — in-memory 16×16 VE map. Computes bilinear interpolation weights, tracks modified cells. Module-level singleton `ve_map_state`.
- `ve_calibration/ve_write_controller.py`: `VeWriteController` — 1-second debounce timer on `ve_adjustment_made`; dispatches `WRITE_ON_MEMORY` command and plays a beep.
- `components/signal_card.py`: `SignalCard` — reusable Qt widget for a labeled numeric value (used in dashboard grid and VE top bar).

**`app/alarm/`** — Limit alarms
- `processor.py`: `AlarmProcessor (QThread)` — polls `vehicle_state.is_any_alarm_firing()` every 100 ms and dispatches play/stop to `QMediaPlayer` via `QueuedConnection`. Emits `Signal` when a new alarm fires (pending connection to dashboard visual flash).

**`app/event/`** — Keyboard-triggered actions (exist, not all wired yet)
- `marker.py`: `EventMarker (QObject)` — filters `Key_Return`/`Key_Enter`, plays a one-shot beep, emits `event_triggered` to `LogWriter`.
- `key_hold_detector.py`: `KeyHoldDetector (QObject)` — generic hold detector. Emits `triggered` after a key is held for the configured duration. Auto-repeat safe.
- `lambda_toggle.py`: `LambdaToggle (QObject)` — reads `vehicle_state.is_lambda_loop_closed()`, plays a sound, emits `command_requested(EcuCommand)`.

**`app/log_writer/`** — CSV logging
- `log_writer.py`: `LogWriter (QObject)` owns a `Worker` moved to a dedicated `QThread`. CSV columns: `Timestamp; Event; <ECU fields...>`. `set_event_pending()` marks the next row with `"MARK"`.

**`app/config.py`** — Configuration
- Loads `config.json` on import and exposes a module-level `config: AppConfig` instance with nested sub-configs for `connection`, `alarm`, `dashboard`, and `ve_calibration`.

**`app/logger.py`** — Logging setup
- `setup_logging()`: configures `logging.basicConfig`. Called once at the top of `main()`.

## Adding or modifying signals

1. Add/edit an entry in the `Signal` enum in `app/masterinjection/signal.py`.
2. Add it to `config.json` under `dashboard.grid` and/or `dashboard.graph` (use the enum member name as the string key).

For calculated signals (no direct CSV column), set `"calculated": True` and provide a `"value"` lambda that receives the already-parsed `parsed_data` dict. Order in the enum matters — calculated signals must come after all their dependencies.

## Adding keyboard-triggered actions

- **Instant actions** (single key press): override `keyPressEvent` in the target `Screen` subclass and filter by key code. For global actions, handle in `AppWindow.keyPressEvent` before delegating.
- **Hold actions** (key held N seconds): create a `KeyHoldDetector(key, hold_ms)`, connect `AppWindow.key_event` → `on_key_pressed` and `AppWindow.key_released` → `on_key_released`, then connect `triggered` to your action. Wire in `main.py`.

## Sending commands to the ECU

Call `get_ecu_connection().send_command(cmd: EcuCommand)` from any thread — it's queued internally and sent after the next complete frame. Add new commands to `EcuCommand` in `app/masterinjection/protocol.py`.

## ECU serial protocol

The ECU streams two frame types per cycle:
- `#D01;val1;val2;...` — primary sensor data
- `#D02;val1;val2;...` — secondary sensor data

`EcuConnectionSerial` waits for one of each, joins them with `;`, and emits the combined string. `SignalProcessor` accesses fields by absolute index across this combined string. Only `#D01`-prefixed lines are logged to CSV.
