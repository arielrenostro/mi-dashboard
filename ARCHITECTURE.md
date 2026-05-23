# Architecture — MI Dashboard

Real-time automotive ECU telemetry dashboard for the Master Injection ECU. Reads data over Bluetooth serial (Windows COM port), parses semicolon-delimited frames, displays live values and graphs, plays audio alarms, logs to CSV, and supports multi-screen keyboard navigation and VE map calibration.

## Stack

- **Python 3.x**
- **PyQt6** — UI framework, threading model (`QThread`, `QObject`, `pyqtSignal`/`@Slot`), media playback (`QMediaPlayer`)
- **pyqtgraph** — real-time signal graphs
- **pyserial** — serial COM port communication

## Entry point

`main.py` — instantiates components, wires signals/slots, and starts the Qt event loop. The CSV log path is hardcoded here; all other settings are loaded from `config.json` via `app/config.py`.

## Module map

```
app/
├── ecu_connection/       # Serial I/O (abstract base + serial + mock + thread)
├── masterinjection/      # Domain models: signals, ECU protocol
├── state/                # Global shared state + processors
│   └── processors/       # Signal-driven state processors (e.g. lambda loop)
├── alarm/                # Limit alarm engine
├── event/                # Keyboard-triggered actions
├── log_writer/           # CSV logging
├── ui/                   # Qt UI
│   ├── base/             # Screen base class
│   ├── components/       # Reusable widgets
│   ├── dashboard/        # Live telemetry screen
│   ├── home/             # Home/menu screen
│   └── ve_calibration/   # VE map calibration screen + state + write controller
├── config.py             # config.json loader
└── logger.py             # Logging setup
```

## Data flow

```
EcuConnectionSerial / EcuConnectionMock
    │  (via EcuConnectionThread : QThread)
    │  emitter(str)  —  "#D01;...;#D02;..."
    ├──► SignalProcessor.process_line()
    │         │  emitter(dict)  —  {Signal: ParsedSignal}
    │         ├──► DashboardScreen.on_signal_received()        UI refresh
    │         ├──► AlarmProcessor.process_signals()            limit check
    │         ├──► VehicleState.update()                       shared state
    │         ├──► LambdaLoopStateProcessor.on_signal_received() loop state
    │         └──► VeCalibrationScreen.process_signals()       top bar update
    └──► LogWriter.write()                                     CSV append

AlarmProcessor.emitter(Signal) ──► [pending] DashboardScreen.fire_field_alarm()

AppWindow.keyPressEvent / keyReleaseEvent ──► current Screen
    HomeScreen:          ↑/↓ navigate menu, Enter open screen
    DashboardScreen:     (no key actions active yet)
    VeCalibrationScreen: ↑/↓ adjust VE, R reset VE, ESC → AppWindow.go_home()

[pending] AppWindow.key_event(int) ──► EventMarker.handle_key()
                                   └──► KeyHoldDetector.on_key_pressed()
[pending] AppWindow.key_released(int) ──► KeyHoldDetector.on_key_released()
              └─ (after 2 s hold) triggered ──► LambdaToggle.handle_trigger()
                                                    ├─ command_requested ──► EcuConnection.send_command()
                                                    └─ command_requested ──► LambdaLoopStateProcessor.on_command_received()
```

All cross-thread communication goes through `pyqtSignal` + `@Slot`. No UI calls from background threads. `QMediaPlayer` is always called from the main thread via `QueuedConnection`.

## ECU serial protocol

```
#D01;val1;val2;...   — primary sensor data
#D02;val1;val2;...   — secondary sensor data
```

`EcuConnectionSerial` waits for one of each, joins them with `;`, and emits the combined string. `SignalProcessor` accesses fields by absolute index across this combined string. Only lines starting with `#D01` are parsed and logged.

Handshake sequence: `#D50` (connect) → `#D01` (start streaming).

## Modules

### `app/ecu_connection/`

| File | Class | Role |
|---|---|---|
| `ecu_connection.py` | `EcuConnection` (ABC) | Abstract base: `send_command()`, `run()`, `start()`, `stop()`, `is_connected()` |
| `serial.py` | `EcuConnectionSerial` | Connects to COM port, sends handshake, buffers and emits joined frames. Reconnects after 3 consecutive empty reads. Thread-safe `send_command()` via internal `queue.Queue`. |
| `mock_log.py` | `EcuConnectionMock` | Replays a CSV log file, timed by embedded timestamps. `send_command()` is a no-op. |
| `thread.py` | `EcuConnectionThread(QThread)` | Wraps any `EcuConnection`, owns the `emitter(str)` pyqtSignal, calls `run()` in a loop. |
| `__init__.py` | — | Module-level registry: `register_ecu_connection()`, `get_ecu_connection()`, `get_ecu_connection_thread()`. |

### `app/masterinjection/`

| File | Contents |
|---|---|
| `signal.py` | `Signal` enum — single source of truth for every ECU signal. Each entry: `index`, `converter`, `for_label`, `unit`, `min`/`max`, `color`, `alarm`. Signals with `calculated: True` derive their value via a `"value"` lambda over already-parsed data. Order matters — calculated signals must follow their dependencies. |
| `signal_processor.py` | `SignalProcessor(QObject)` — splits the joined frame on `;`, iterates all `Signal` members, applies converters, builds `parsed_data` dict, emits it. |
| `protocol.py` | `EcuCommand` / `EcuResponse` enums. Each `EcuCommand` entry has `.cmd` (wire string) and `.description`. |

### `app/state/`

| File | Class | Role |
|---|---|---|
| `state.py` | `VehicleState` | Thread-safe store (via `threading.RLock`) for latest signal values, alarm timestamps, effective lambda loop state, RPM/MAP breakpoints, and VE map. Module-level singleton `vehicle_state`. Emits `VehicleStateChangeEvent` on breakpoint/VE map updates. |
| `processors/lambda_loop_state.py` | `LambdaLoopStateProcessor` | Determines effective lambda loop state, filtering transient open-loop during deceleration fuel cut. Rule: "closed" always fact; "open" only when `PEDAL == 0 AND MAP ≤ 20 kPa`. `on_command_received()` updates state immediately on toggle. |
| `event.py` | `VehicleStateChangeEvent` | Typed event (`EventType` enum) emitted by `VehicleState` for breakpoint and VE map changes. |

### `app/ui/`

| File | Class | Role |
|---|---|---|
| `window.py` | `AppWindow(QWidget)` | Full-screen window with `QStackedWidget`. Self-registers all screens. Routes key events to the active screen. `show_screen(name)` calls lifecycle hooks. `ESC` always calls `go_home()`. |
| `base/screen.py` | `Screen(QWidget)` | Base class. Lifecycle: `on_activated()`, `on_deactivated()` (no-ops by default). |
| `home/screen.py` | `HomeScreen` | Vertical menu. `↑`/`↓` navigation, `Enter` to select. Emits `screen_requested(str)`. |
| `dashboard/screen.py` | `DashboardScreen` | Numeric grid + multi-plot graphs. Layout from `config.json`. Graph buffers in `deque`, refreshed every 100 ms via `QTimer`. |
| `ve_calibration/screen.py` | `VeCalibrationScreen` | Top-bar signals, 16×16 VE table, pyqtgraph heatmap. `↑`/`↓` edits VE; `R` resets. Emits `ve_adjustment_made`. |
| `ve_calibration/ve_map_state.py` | `VeMapState` | In-memory 16×16 VE map. Bilinear interpolation weights, `adjust_ve()`, `reset()`, `modified_cells` tracking. Singleton `ve_map_state`. |
| `ve_calibration/ve_write_controller.py` | `VeWriteController` | 1-second debounce on `ve_adjustment_made`; sends `WRITE_ON_MEMORY` and plays a beep. |
| `components/signal_card.py` | `SignalCard` | Reusable labeled numeric value widget. |

### `app/alarm/`

| File | Class | Role |
|---|---|---|
| `processor.py` | `AlarmProcessor(QThread)` | Polls `vehicle_state.is_any_alarm_firing()` every 100 ms. Dispatches play/stop to `QMediaPlayer` via `QueuedConnection`. Emits `Signal` when a new alarm fires (pending dashboard connection). |

### `app/event/`

| File | Class | Role |
|---|---|---|
| `marker.py` | `EventMarker(QObject)` | Filters `Key_Return`/`Key_Enter`, plays a one-shot beep, emits `event_triggered` to `LogWriter`. *(pending wiring)* |
| `key_hold_detector.py` | `KeyHoldDetector(QObject)` | Generic hold detector. Emits `triggered` after key held for configured ms. Auto-repeat safe. *(pending wiring)* |
| `lambda_toggle.py` | `LambdaToggle(QObject)` | Reads lambda loop state, plays sound, emits `command_requested(EcuCommand)`. *(pending wiring)* |

### `app/log_writer/`

| File | Class | Role |
|---|---|---|
| `log_writer.py` | `LogWriter(QObject)` | Owns a `Worker` moved to a dedicated `QThread`. CSV: `Timestamp; Event; <ECU fields…>`. `set_event_pending()` marks the next row with `"MARK"`. |

## Signals (ECU telemetry fields)

| Signal | Index | Unit | Alarm |
|---|---|---|---|
| RPM | 1 | RPM | max 6600 |
| MAP | 2 | kPa | max 165 |
| Boost | 3 | kPa | disabled |
| λ (Lambda) | 6 | λ | disabled |
| Inj. Duty | 8 | % | max 90 |
| VE | 9 | % | disabled |
| Ign | 10 | º | disabled |
| CLT | 19 | ºC | max 95 |
| IAT | 20 | ºC | disabled |
| Speed | 23 | km/h | max 150 |
| λ Loop | 24 | — | disabled |
| λ Target | 25 | λ | disabled |
| Fuel Trim | 26 | % | ±20 |
| Boost Target | 28 | kPa | disabled |
| Pedal | 29 | % | disabled |
| Gear | 33 | — | disabled |
| **Power** | calculated | HP | disabled |
| **Torque** | calculated | Kgf.m | disabled |

`Power` and `Torque` are derived from MAP, VE, RPM, IAT, and Lambda.

## Threading model

| Thread | Owner | Responsibility |
|---|---|---|
| Main (Qt event loop) | `QApplication` | UI rendering, slot dispatch, `QMediaPlayer` |
| ECU reader | `EcuConnectionThread` | Blocking serial I/O or CSV replay |
| Alarm poller | `AlarmProcessor` | 100 ms polling loop for audio control |
| Log writer | `LogWriter` internal `QThread` | Disk I/O (CSV append) |

Inter-thread communication: only via `pyqtSignal` + `@Slot`. The only shared mutable state is `VehicleState`, protected by `threading.RLock`. `EcuConnection.send_command()` is thread-safe via `queue.Queue`.

## Extending the project

**Add a new signal:** add an entry to `Signal` in `app/masterinjection/signal.py`, then add it to the grid/graph lists in `config.json`.

**Add a calculated signal:** set `"calculated": True`, provide a `"value"` lambda over `parsed_data`, and place it after all its dependencies in the enum.

**Add an instant keyboard action on a specific screen:** override `keyPressEvent` in the target `Screen` subclass.

**Add a hold keyboard action:** create `KeyHoldDetector(key, hold_ms)`, connect `AppWindow.key_event` → `on_key_pressed` and `AppWindow.key_released` → `on_key_released`, connect `triggered` to your handler. Wire in `main.py`.

**Send a command to the ECU:** call `get_ecu_connection().send_command(cmd: EcuCommand)` from any thread. Add new commands to `EcuCommand` in `app/masterinjection/protocol.py`.
