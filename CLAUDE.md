# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Real-time automotive ECU telemetry dashboard for the Master Injection ECU. It reads data over a Bluetooth serial COM port (Windows), parses semicolon-delimited frames, displays live signal values and graphs, plays audio alarms, logs raw data to CSV, and supports manual event marking via keyboard.

## Running the app

```
.venv\Scripts\python main.py
```

No build step. No test suite. Dependencies:

```
pip install -r requirements.txt   # pyserial, pyqt6, pyqtgraph
```

## Configuration (all in `main.py`)

| Variable | Purpose |
|---|---|
| `PORT` | Windows COM port (e.g. `"COM5"`) |
| `BAUDRATE` | Serial baud rate |
| `LOG_FILE` | Output CSV path |
| `ALARM_SOUND` | Path to `.wav` file for limit alarms |
| `EVENT_SOUND` | Path to `.wav` file for ENTER key marker beep |
| `MOCK_FILE` | If set (non-empty), uses `EcuConnectionMock` instead of real serial |

To run without hardware, set `MOCK_FILE` to a previously recorded CSV log.

All other values (signal indices, limits, layout) are intentionally hardcoded — this is a personal script.

## Architecture

### Data flow

```
EcuConnection / EcuConnectionMock (QThread)
    │  emitter(str)  — raw semicolon-joined #D01;#D02 line
    ├──► SignalProcessor.process_line()
    │         │  emitter(dict)  — {Signal: {value, value_str, raw, signal}}
    │         ├──► Dashboard.process_signals()             (UI update)
    │         ├──► AlarmProcessor.process_signals()         (alarm check)
    │         ├──► VehicleState.update()                   (global state snapshot)
    │         └──► LambdaLoopStateProcessor.process_signals() (effective loop state)
    └──► LogWriter.write()                                 (CSV append)

AlarmProcessor.emitter(Signal) ──► Dashboard.fire_field_alarm()   (visual flash)

Dashboard.key_event(int) ──► EventMarker.handle_key()
                         │       ├─ QMediaPlayer.play()             (event beep)
                         │       └─ EventMarker.event_triggered ──► LogWriter.set_event_pending()
                         └──► KeyHoldDetector.on_key_pressed()
Dashboard.key_released(int) ──► KeyHoldDetector.on_key_released()
                                    └─ (after 2 s) triggered ──► LambdaToggle.handle_trigger()
                                                                       ├─ QMediaPlayer.play()
                                                                       ├─ command_requested ──► EcuConnection.send_command()
                                                                       └─ command_requested ──► LambdaLoopStateProcessor.on_command_sent()
```

All cross-thread communication goes through `pyqtSignal` / `@Slot`. The UI is never touched from background threads. `QMediaPlayer` calls are always dispatched to the main thread via `Qt.ConnectionType.QueuedConnection`.

### Modules

**`app/ecu_connection/`** — ECU communication  
- `EcuConnection`: QThread that connects to the ECU, sends `#D50` (handshake) then `#D01` (start streaming). Buffers `#D01` and `#D02` lines and emits them joined as `"#D01...;#D02..."`. Reconnects automatically after 3 consecutive empty reads. Exposes `send_command(cmd: EcuCommand)` — thread-safe: queues the command and drains after each complete frame.  
- `EcuConnectionMock`: Replays a CSV log file, timing emissions based on embedded timestamps when available. `send_command()` is a no-op.

**`app/master/`** — Domain models  
- `signal.py`: `Signal` enum — the single source of truth for every ECU signal. Each entry defines `index` (CSV column), `converter` (raw→value), `for_label` (value→display string), `unit`, `min`/`max` (graph range), `color`, and `alarm` config. Signals with `calculated: True` (e.g. `POWER`, `TORQUE`) derive their value from other already-parsed signals via a `value` lambda.  
- `signal_processor.py`: `SignalProcessor (QObject)` — splits the joined line on `;`, iterates all `Signal` enum members, applies converters, builds the `parsed_data` dict, and emits it.  
- `ecu.py`: `EcuCommand` / `EcuResponse` enums for the serial protocol.  
- `log.py`: `LOG_PREFIX = "#D01"` — only lines starting with this are parsed/logged.

**`app/vehicle/`** — Global vehicle state  
- `state.py`: `VehicleState` class with `threading.RLock`. Stores the latest `parsed_data` dict for every signal (`update()` / `get()` / `get_all()`), alarm timestamps (`is_alarm_firing()` / `set_alarm()`), and the effective lambda loop state (`is_lambda_loop_closed()` / `set_lambda_loop_state()`). Module-level instance `vehicle_state` imported everywhere.  
- `lambda_loop_state_processor.py`: `LambdaLoopStateProcessor (QObject)` — determines the effective lambda loop state from ECU data, filtering out transient open-loop periods caused by deceleration (fuel cut). Logic: "closed" from ECU is always fact; "open" is only accepted when `PEDAL == 0 AND MAP ≤ 20 kPa` is false. `on_command_sent()` updates the state immediately when a toggle command is dispatched.

**`app/dashboard/`** — Qt UI  
- `dashboard.py`: Full-screen `QWidget`. Emits `key_event(int)` on key press and `key_released(int)` on key release (both carry the `Qt.Key` int value). Graph data buffered in `deque(maxlen=graph_x_size)`, refreshed every 100 ms via `QTimer`.  
- `grid.py`: `GRID` (2D list of Signals for the numeric grid) and `GRAPH` (list of rows, each row a list of Signals sharing one plot).

**`app/alarm/`** — Limit alarms  
- `processor.py`: `AlarmProcessor (QThread)` — polls `vehicle_state.is_any_alarm_firing()` every 100 ms and dispatches play/stop to `QMediaPlayer` via `QueuedConnection` signals to respect thread affinity. Emits a `Signal` to the dashboard when a new alarm fires.

**`app/event/`** — Keyboard-triggered actions  
- `marker.py`: `EventMarker (QObject)` — filters `Key_Return`/`Key_Enter` from `Dashboard.key_event`, plays a one-shot beep via `QMediaPlayer`, and emits `event_triggered` to notify `LogWriter`.  
- `key_hold_detector.py`: `KeyHoldDetector (QObject)` — generic hold detector. Configured with a target key and hold duration (ms). Connects to `Dashboard.key_event` and `Dashboard.key_released`; emits `triggered` after the key is held for the configured duration. Auto-repeat safe: timer is not restarted if already running.  
- `lambda_toggle.py`: `LambdaToggle (QObject)` — handles lambda loop toggle. Plays a sound, reads `vehicle_state.is_lambda_loop_closed()` to determine current state, and emits `command_requested(EcuCommand)` with the appropriate command.

**`app/log_writer/`** — CSV logging  
- `log_writer.py`: `LogWriter (QObject)` owns a `Worker (QObject)` moved to a dedicated `QThread`. CSV columns: `Timestamp; Event; <ECU fields...>`. The `Event` column is normally empty; calling `set_event_pending()` marks the next written row with `"MARK"`.

**`app/logger.py`** — Logging setup  
- `setup_logging()`: configures `logging.basicConfig` with format `HH:MM:SS [LEVEL] module: message`. Called once at the top of `main()`.

## Adding or modifying signals

1. Add/edit an entry in the `Signal` enum in `app/master/signal.py`.
2. Add it to `GRID` and/or `GRAPH` in `app/dashboard/grid.py`.

For calculated signals (no direct CSV column), set `"calculated": True` and provide a `"value"` lambda that receives the already-parsed `parsed_data` dict. Order in the enum matters — calculated signals must come after all their dependencies.

## Adding keyboard-triggered actions

- **Instant actions** (single key press): connect a new `QObject` to `Dashboard.key_event(int)` and filter by key code.
- **Hold actions** (key held N seconds): create a `KeyHoldDetector(key, hold_ms)`, connect `Dashboard.key_event` → `on_key_pressed` and `Dashboard.key_released` → `on_key_released`, then connect `triggered` to your action. Wire in `main.py`.

## Sending commands to the ECU

Call `ecu_connection.send_command(cmd: EcuCommand)` from any thread — it's queued internally and sent after the next complete frame. Add new commands to `EcuCommand` in `app/master/ecu.py`.

## ECU serial protocol

The ECU streams two frame types per cycle:
- `#D01;val1;val2;...` — primary sensor data
- `#D02;val1;val2;...` — secondary sensor data

`EcuConnection` waits for one of each, joins them with `;`, and emits the combined string. `SignalProcessor` accesses fields by absolute index across this combined string.
