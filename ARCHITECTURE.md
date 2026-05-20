# Architecture — MI Dashboard

Real-time automotive ECU telemetry dashboard for the Master Injection ECU. Reads data over Bluetooth serial (Windows COM port), parses semicolon-delimited frames, displays live values and graphs, plays audio alarms, logs to CSV, and supports keyboard-triggered events.

## Stack

- **Python 3.x**
- **PyQt6** — UI framework, threading model (`QThread`, `QObject`, `pyqtSignal`/`@Slot`), media playback (`QMediaPlayer`)
- **pyqtgraph** — real-time signal graphs
- **pyserial** — serial COM port communication

## Entry point

`main.py` — instantiates all components, wires signals/slots, and starts the Qt event loop. Configuration constants (`PORT`, `BAUDRATE`, `LOG_FILE`, `MOCK_FILE`, etc.) live here.

## Module map

```
app/
├── ecu_connection/       # Serial I/O (real and mock)
├── master/               # Domain models: signals, ECU protocol
├── vehicle/              # Global shared state
├── dashboard/            # Qt UI
├── alarm/                # Limit alarm engine
├── event/                # Keyboard-triggered actions
├── log_writer/           # CSV logging
└── logger.py             # Logging setup
```

## Data flow

```
EcuConnection / EcuConnectionMock  (QThread)
    │  emitter(str)  —  "#D01;...;#D02;..."
    ├──► SignalProcessor.process_line()
    │         │  emitter(dict)  —  {Signal: {value, value_str, raw, signal}}
    │         ├──► Dashboard.process_signals()              UI refresh
    │         ├──► AlarmProcessor.process_signals()          limit check
    │         ├──► VehicleState.update()                    shared state
    │         └──► LambdaLoopStateProcessor.process_signals() loop state
    └──► LogWriter.write()                                  CSV append

AlarmProcessor.emitter(Signal) ──► Dashboard.fire_field_alarm()    visual flash

Dashboard.key_event(int) ──► EventMarker.handle_key()
                         │       ├─ QMediaPlayer.play()
                         │       └─ event_triggered ──► LogWriter.set_event_pending()
                         └──► KeyHoldDetector.on_key_pressed()
Dashboard.key_released(int) ──► KeyHoldDetector.on_key_released()
                                    └─ (after 2 s hold) triggered ──► LambdaToggle.handle_trigger()
                                                                           ├─ QMediaPlayer.play()
                                                                           ├─ command_requested ──► EcuConnection.send_command()
                                                                           └─ command_requested ──► LambdaLoopStateProcessor.on_command_sent()
```

All cross-thread communication goes through `pyqtSignal` / `@Slot`. `QMediaPlayer` calls are dispatched to the main thread via `Qt.ConnectionType.QueuedConnection`.

## ECU serial protocol

The ECU streams two frame types per cycle:

```
#D01;val1;val2;...   — primary sensor data
#D02;val1;val2;...   — secondary sensor data
```

`EcuConnection` waits for one of each, joins them with `;`, and emits the combined string. `SignalProcessor` accesses fields by absolute index across this combined string. Only lines starting with `#D01` are parsed and logged (`LOG_PREFIX` in `app/master/log.py`).

Handshake sequence: `#D50` (connect) → `#D01` (start streaming).

## Modules

### `app/ecu_connection/`

| File | Class | Role |
|---|---|---|
| `ecu_connection.py` | `EcuConnection(QThread)` | Connects to COM port, sends handshake, buffers and emits joined frames. Reconnects after 3 consecutive empty reads. Thread-safe `send_command()` — queued and drained after each complete frame. |
| `ecu_connection_mock.py` | `EcuConnectionMock(QThread)` | Replays a CSV log file. Emits frames timed by embedded timestamps. `send_command()` is a no-op. |

### `app/master/`

| File | Contents |
|---|---|
| `signal.py` | `Signal` enum — single source of truth for every ECU signal. Each entry: `index`, `converter` (raw→value), `for_label` (value→display string), `unit`, `min`/`max`, `color`, `alarm`. Signals with `calculated: True` (e.g. `POWER`, `TORQUE`) derive their value via a `value` lambda over already-parsed data. Order in enum matters — calculated signals must follow their dependencies. |
| `signal_processor.py` | `SignalProcessor(QObject)` — splits the joined frame on `;`, iterates all `Signal` members, applies converters, builds `parsed_data` dict, emits it. |
| `ecu.py` | `EcuCommand` / `EcuResponse` enums for the serial protocol. |
| `log.py` | `LOG_PREFIX = "#D01"` |

### `app/vehicle/`

| File | Class | Role |
|---|---|---|
| `state.py` | `VehicleState` | Thread-safe store (via `threading.RLock`) for latest signal values, alarm timestamps, and effective lambda loop state. Module-level singleton `vehicle_state` imported everywhere. |
| `lambda_loop_state_processor.py` | `LambdaLoopStateProcessor(QObject)` | Determines effective lambda loop state, filtering transient open-loop caused by deceleration fuel cut. Rule: "closed" from ECU is always fact; "open" is only accepted when `PEDAL == 0 AND MAP ≤ 20 kPa` is false. |

### `app/dashboard/`

| File | Contents |
|---|---|
| `dashboard.py` | `Dashboard(QWidget)` — full-screen Qt UI. Emits `key_event(int)` on press and `key_released(int)` on release. Graph data in `deque(maxlen=graph_x_size)`, refreshed every 100 ms via `QTimer`. |
| `grid.py` | `GRID` (2-D list of Signals for the numeric grid) and `GRAPH` (list of rows, each a list of Signals sharing one plot). |

### `app/alarm/`

| File | Class | Role |
|---|---|---|
| `processor.py` | `AlarmProcessor(QThread)` | Polls `vehicle_state.is_any_alarm_firing()` every 100 ms. Dispatches play/stop to `QMediaPlayer` via `QueuedConnection`. Emits `Signal` to dashboard when a new alarm fires. |

### `app/event/`

| File | Class | Role |
|---|---|---|
| `marker.py` | `EventMarker(QObject)` | Filters `Key_Return`/`Key_Enter` from `key_event`, plays a one-shot beep, emits `event_triggered` to `LogWriter`. |
| `key_hold_detector.py` | `KeyHoldDetector(QObject)` | Generic hold detector. Configured with a target key and hold duration (ms). Emits `triggered` after the key is held. Auto-repeat safe. |
| `lambda_toggle.py` | `LambdaToggle(QObject)` | Reads current lambda loop state, plays a sound, emits `command_requested(EcuCommand)` with the appropriate toggle command. |

### `app/log_writer/`

| File | Class | Role |
|---|---|---|
| `log_writer.py` | `LogWriter(QObject)` | Owns a `Worker(QObject)` moved to a dedicated `QThread`. CSV columns: `Timestamp; Event; <ECU fields…>`. `set_event_pending()` marks the next written row with `"MARK"`. |

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
| Main (Qt event loop) | `QApplication` | UI rendering, slot dispatch |
| ECU reader | `EcuConnection` / `EcuConnectionMock` | Blocking serial read / CSV replay |
| Alarm poller | `AlarmProcessor` | 100 ms polling loop |
| Log writer | `LogWriter` internal `QThread` | Disk I/O |

Inter-thread communication: only via `pyqtSignal` + `@Slot`. No shared mutable state except `VehicleState`, which is protected by `threading.RLock`.

## Extending the project

**Add a new signal:** add an entry to `Signal` in `app/master/signal.py`, then add it to `GRID` and/or `GRAPH` in `app/dashboard/grid.py`.

**Add a calculated signal:** set `"calculated": True`, provide a `"value"` lambda over `parsed_data`, and place it after all its dependencies in the enum.

**Add an instant keyboard action:** connect a new `QObject` to `Dashboard.key_event(int)` and filter by key code.

**Add a hold keyboard action:** create `KeyHoldDetector(key, hold_ms)`, connect `key_event` → `on_key_pressed` and `key_released` → `on_key_released`, then connect `triggered` to your handler. Wire everything in `main.py`.

**Send a command to the ECU:** call `ecu_connection.send_command(cmd: EcuCommand)` from any thread. Add new commands to `EcuCommand` in `app/master/ecu.py`.
