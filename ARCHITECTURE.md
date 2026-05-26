# Architecture — MI Dashboard

Real-time automotive ECU telemetry dashboard for the Master Injection ECU. Reads data over Bluetooth serial (Windows COM port), parses semicolon-delimited frames, displays live values and graphs, plays audio alarms, logs to CSV, and supports multi-screen keyboard navigation and VE map calibration.

## Stack

- **Python 3.x**
- **PyQt6** — UI framework, threading model (`QThread`, `QObject`, `pyqtSignal`/`@Slot`), media playback (`QMediaPlayer`)
- **pyqtgraph** — real-time signal graphs
- **pyserial** — serial COM port communication

## Entry point

`main.py` — instantiates components, wires signals/slots and bus subscriptions, and starts the Qt event loop. All settings are loaded from `config.json` via `app/config.py`.

## Module map

```
app/
├── ecu_connection/       # Serial I/O (abstract base + serial + mock + thread)
├── masterinjection/      # Domain models: signals, ECU protocol
├── state/                # Global shared state + processors
│   └── processors/       # Signal-driven state processors (e.g. lambda loop)
├── alarm/                # Limit alarm engine
├── event/                # Event bus, typed events, keyboard-triggered actions
├── log_writer/           # CSV logging
├── ui/                   # Qt UI
│   ├── base/             # Screen base class (bus subscription helpers)
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
    │         │  emitter(dict)  +  event_bus → SIGNALS_RECEIVED
    │         │
    │         │  Bus subscribers:
    │         ├──► AlarmProcessor.process_signals()        limit check + AlarmFiredEvent
    │         ├──► VehicleState.update()                   shared state snapshot
    │         └──► DashboardScreen.on_signal_received()    UI refresh  (only when active)
    │
    │         VeCalibrationScreen reads vehicle_state via 100 ms QTimer
    │
    └──► LogWriter.write()   (raw string, not parsed)      CSV append

event_bus → ALARM_FIRED    ──► DashboardScreen.fire_field_alarm()   (only when active)
event_bus → SCREEN_REQUESTED ──► AppWindow.show_screen()

AppWindow.keyPressEvent / keyReleaseEvent ──► current Screen (direct dispatch)
    HomeScreen:           ↑/↓ navigate menu, Enter → SCREEN_REQUESTED on bus
    DashboardScreen:      ESC → close_fn()
    VeCalibrationScreen:  ↑/↓ adjust VE, R reset VE, O/P lambda loop, ESC → close_fn()

AppWindow.key_event(int)    ──► EventMarker.handle_key()      → EVENT_MARK_REQUESTED on bus
                            └──► KeyHoldDetector.on_key_pressed()
AppWindow.key_released(int) ──► KeyHoldDetector.on_key_released()
    └─ (after 2 s hold) triggered ──► LambdaToggle.handle_trigger()
                                          └─ ECU_COMMAND_REQUESTED on bus
                                               ├──► EcuConnection.send_command()
                                               └──► LambdaLoopStateProcessor.on_command_received()

event_bus → EVENT_MARK_REQUESTED ──► LogWriter.set_event_pending()
```

All cross-thread communication goes through `pyqtSignal` + `@Slot` or the `EventBus`. No UI calls from background threads. `QMediaPlayer` is always called from the main thread via `QueuedConnection`.

## Event Bus

`app/event/bus.py` — singleton `event_bus`. One dedicated `pyqtSignal(object)` per event type; Qt dispatches directly to subscribers without per-subscriber `isinstance` filtering.

`app/event/app_events.py` — `AppEventType` enum + frozen dataclasses:

| Type | Dataclass | Key fields |
|---|---|---|
| `SCREEN_REQUESTED` | `ScreenRequestedEvent` | `screen_name: str` |
| `ECU_COMMAND_REQUESTED` | `EcuCommandRequestedEvent` | `command`, `args` |
| `ALARM_FIRED` | `AlarmFiredEvent` | `signal`, `until: float` |
| `VEHICLE_STATE_CHANGED` | `VehicleStateChangedEvent` | `change_type`, `args` |
| `EVENT_MARK_REQUESTED` | `EventMarkRequestedEvent` | — |
| `SIGNALS_RECEIVED` | `SignalsReceivedEvent` | `data: dict` |

Keyboard events bypass the bus — they are wired directly via `AppWindow.key_event` / `key_released` pyqtSignals to avoid global propagation.

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
| `signal.py` | `Signal` enum — single source of truth. Each entry: `index`, `converter`, `for_label`, `unit`, `min`/`max`, `color`, `alarm` (with optional `duration_s`). Calculated signals use a `"value"` lambda over `parsed_data`. |
| `signal_processor.py` | `SignalProcessor(QObject)` — splits the frame, builds `parsed_data`, emits via legacy `emitter(dict)` and publishes `SignalsReceivedEvent` to the bus. |
| `protocol.py` | `EcuCommand` / `EcuResponse` enums. Each `EcuCommand` has `.cmd` and `.description`. |

### `app/state/`

| File | Class | Role |
|---|---|---|
| `state.py` | `VehicleState` | Thread-safe store (`threading.RLock`) for latest signal values, alarm timestamps, lambda loop state, RPM/MAP breakpoints, and VE map. Emits `VehicleStateChangeEvent` on map updates. Singleton `vehicle_state`. |
| `processors/lambda_loop_state.py` | `LambdaLoopStateProcessor` | Filters transient open-loop during deceleration fuel cut. `on_command_received()` updates state immediately on toggle. |
| `event.py` | `VehicleStateChangeEvent` | Typed event (`EventType` enum: `MAP_BREAKPOINTS`, `RPM_BREAKPOINTS`, `FUEL_MAP`). |

### `app/event/`

| File | Class | Role |
|---|---|---|
| `app_events.py` | `AppEventType` + dataclasses | All app-level event types as frozen dataclasses. |
| `bus.py` | `EventBus` / `event_bus` | Singleton broker. One `pyqtSignal(object)` per type. `publish()` / `subscribe()` / `unsubscribe()`. Thread-safe via Qt's built-in cross-thread signal delivery. |
| `marker.py` | `EventMarker(QObject)` | Filters `Key_Return`/`Key_Enter`, plays beep, publishes `EventMarkRequestedEvent`. |
| `key_hold_detector.py` | `KeyHoldDetector(QObject)` | Generic hold detector. Emits `triggered` after configured ms. Auto-repeat safe. |
| `lambda_toggle.py` | `LambdaToggle(QObject)` | Reads lambda loop state, plays sound, publishes `EcuCommandRequestedEvent`. |

### `app/ui/`

| File | Class | Role |
|---|---|---|
| `window.py` | `AppWindow(QWidget)` | Full-screen window with `QStackedWidget`. Subscribes to `SCREEN_REQUESTED` on bus. Exposes `key_event(int)` / `key_released(int)` for direct keyboard wiring. |
| `base/screen.py` | `Screen(QWidget)` | Base class. `_subscribe(type, cb)` tracks tokens; `on_deactivated()` auto-unsubscribes all. |
| `home/screen.py` | `HomeScreen` | Vertical menu. `↑`/`↓` navigation, `Enter` publishes `ScreenRequestedEvent`. |
| `dashboard/screen.py` | `DashboardScreen` | Numeric grid + multi-plot graphs. Subscribes to `SIGNALS_RECEIVED` + `ALARM_FIRED` in `on_activated()`; unsubscribes in `on_deactivated()`. |
| `ve_calibration/screen.py` | `VeCalibrationScreen` | Top-bar signals, 16×16 VE table, heatmap. `↑`/`↓` edits VE; `R` resets. Calls `_writer.on_adjustment_made()` directly. |
| `ve_calibration/ve_map_state.py` | `VeMapState` | In-memory 16×16 VE map. Bilinear interpolation weights, `adjust_ve()`, `reset()`, modified cells. Singleton `ve_map_state`. |
| `ve_calibration/ve_write_controller.py` | `VeWriteController` | 1-second debounce; sends pending rows directly via `get_ecu_connection().send_command()`. Plays beep on dispatch. |
| `components/signal_card.py` | `SignalCard` | Reusable labeled numeric value widget. |

### `app/alarm/`

| File | Class | Role |
|---|---|---|
| `processor.py` | `AlarmProcessor(QThread)` | Subscribes to `SIGNALS_RECEIVED`. Per-signal cooldown: publishes one `AlarmFiredEvent` per alarm period (`duration_s`, default 2 s), re-publishes only after `until` expires. Audio loop polls `vehicle_state.is_any_alarm_firing()` every 100 ms. `QMediaPlayer` calls via `QueuedConnection`. |

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

Inter-thread communication: `pyqtSignal` + `@Slot` (including `event_bus` signals). The only shared mutable state is `VehicleState`, protected by `threading.RLock`. `EcuConnection.send_command()` is thread-safe via `queue.Queue`.

## Extending the project

**Add a new signal:** add entry to `Signal` in `app/masterinjection/signal.py`, add to grid/graph in `config.json`.

**Add a calculated signal:** set `"calculated": True`, provide `"value"` lambda over `parsed_data`, place after dependencies.

**Add an app-level event:** add `AppEventType` value + dataclass in `app_events.py`, add `pyqtSignal(object)` to `_EventBusQObject` and entry in `_SIGNAL_ATTR` in `bus.py`.

**Add an instant keyboard action on a specific screen:** override `keyPressEvent` in the target `Screen` subclass.

**Add a hold keyboard action:** create `KeyHoldDetector(key, hold_ms)`, connect `AppWindow.key_event` → `on_key_pressed` and `AppWindow.key_released` → `on_key_released`, connect `triggered` to handler. Wire in `main.py`.

**Send a command to the ECU:** call `get_ecu_connection().send_command(cmd: EcuCommand)`. Add new commands to `EcuCommand` in `app/masterinjection/protocol.py`.
