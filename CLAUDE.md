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

Settings are loaded from `config.json` in the project root. If the file is absent, built-in defaults apply.

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
    │         │  emitter(dict) + event_bus(SIGNALS_RECEIVED)
    │         │    Subscribers via bus:
    │         │    ├──► AlarmProcessor.process_signals()     (alarm check + AlarmFiredEvent)
    │         │    ├──► VehicleState.update()                (global state snapshot)
    │         │    └──► DashboardScreen.on_signal_received() (UI update, only when active)
    │         └──  VeCalibrationScreen reads vehicle_state via timer (100 ms)
    └──► LogWriter.write()                                  (CSV append, raw line)

event_bus(ALARM_FIRED)    ──► DashboardScreen.fire_field_alarm()  (only when active)
event_bus(SCREEN_REQUESTED) ──► AppWindow.show_screen()

AppWindow  dispatches keyPressEvent / keyReleaseEvent  ──► current Screen
    VeCalibrationScreen.keyPressEvent():  ↑/↓ → adjust VE,  G → % dialog,  R → reset VE
    HomeScreen.keyPressEvent():           ↑/↓ → nav,  Enter → ScreenRequestedEvent via bus
    AppWindow.keyPressEvent():            ESC → go_home()

AppWindow.key_event(int) ──► EventMarker.handle_key()   → EventMarkRequestedEvent via bus
                         └──► KeyHoldDetector.on_key_pressed()
AppWindow.key_released(int) ──► KeyHoldDetector.on_key_released()
    └─ (after 2 s hold) triggered ──► LambdaToggle.handle_trigger()
                                          └─ EcuCommandRequestedEvent via bus
                                               ├──► EcuConnection.send_command()
                                               └──► LambdaLoopStateProcessor.on_command_received()

event_bus(EVENT_MARK_REQUESTED) ──► LogWriter.set_event_pending()
```

All cross-thread communication goes through `pyqtSignal` / `@Slot` or the `EventBus`. The UI is never touched from background threads. `QMediaPlayer` calls are always dispatched to the main thread via `Qt.ConnectionType.QueuedConnection`.

### Event Bus

The central event broker lives at `app/event/bus.py` as the module-level singleton `event_bus`. It has one `pyqtSignal(object)` per event type — Qt dispatches directly to subscribers of that type with no per-subscriber filtering.

Event types and dataclasses are defined in `app/event/app_events.py`:

| `AppEventType` | Dataclass | Payload |
|---|---|---|
| `SCREEN_REQUESTED` | `ScreenRequestedEvent` | `screen_name: str` |
| `ECU_COMMAND_REQUESTED` | `EcuCommandRequestedEvent` | `command: EcuCommand`, `args: Any` |
| `ALARM_FIRED` | `AlarmFiredEvent` | `signal: Signal`, `until: float` (unix ts) |
| `VEHICLE_STATE_CHANGED` | `VehicleStateChangedEvent` | `change_type: EventType`, `args: tuple` |
| `EVENT_MARK_REQUESTED` | `EventMarkRequestedEvent` | — |
| `SIGNALS_RECEIVED` | `SignalsReceivedEvent` | `data: Dict[Signal, ParsedSignal]` |

Screens inherit `Screen._subscribe(event_type, callback)` which tracks tokens automatically. `on_deactivated()` on the base class unsubscribes all tokens — screens subscribe in `on_activated()` for transient subscriptions.

Keyboard events (`key_event`, `key_released`) are **not** routed through the bus — they are wired directly via `pyqtSignal` in `main.py` to avoid global propagation.

### Modules

**`app/ecu_connection/`** — ECU communication
- `ecu_connection.py`: Abstract `EcuConnection` base class. Defines `send_command(cmd, args)`, `run()`, `start()`, `stop()`, `is_connected()`.
- `serial.py`: `EcuConnectionSerial` — connects to the COM port, sends `#D50` (handshake) then `#D01` (start streaming). Buffers `#D01` and `#D02` lines and emits them joined as `"#D01...;#D02..."`. Reconnects after 3 consecutive empty reads. `send_command()` is thread-safe via an internal `queue.Queue`, drained after each complete frame.
- `mock_log.py`: `EcuConnectionMock` — replays a CSV log file, timing emissions based on embedded timestamps. `send_command()` is a no-op.
- `thread.py`: `EcuConnectionThread (QThread)` — wraps any `EcuConnection` and owns the `emitter(str)` pyqtSignal. Calls `ecu_connection.run()` in a loop.
- `__init__.py`: Module-level `register_ecu_connection()` / `get_ecu_connection()` / `get_ecu_connection_thread()` registry.

**`app/masterinjection/`** — Domain models
- `signal.py`: `Signal` enum — the single source of truth for every ECU signal. Each entry defines `index` (CSV column position in the combined frame), `converter` (raw→value), `for_label` (value→display string), `unit`, `min`/`max` (graph range), `color`, and `alarm` config. Alarm config includes optional `"duration_s"` (default 2.0 s) controlling alarm event cooldown. Signals with `calculated: True` (e.g. `POWER`, `TORQUE`) derive their value via a `"value"` lambda over already-parsed data.
- `signal_processor.py`: `SignalProcessor (QObject)` — splits the joined line on `;`, iterates all `Signal` enum members, applies converters, builds the `parsed_data` dict, emits it via the legacy `emitter(dict)` and publishes `SignalsReceivedEvent` to the bus.
- `protocol.py`: `EcuCommand` / `EcuResponse` enums for the serial protocol. `EcuCommand` entries include `cmd` (the wire string) and `description`.

**`app/state/`** — Global vehicle state
- `state.py`: `VehicleState` with `threading.RLock`. Stores the latest signal snapshot, alarm timestamps, effective lambda loop state, and ECU map data. Emits `VehicleStateChangeEvent` on breakpoint/VE map updates. Module-level singleton `vehicle_state`.
- `processors/lambda_loop_state.py`: `LambdaLoopStateProcessor` — filters transient open-loop during deceleration fuel cut.
- `event.py`: `VehicleStateChangeEvent` + `EventType` enum for typed state-change notifications.

**`app/ui/`** — Qt UI
- `window.py`: `AppWindow (QWidget)` — full-screen window with a `QStackedWidget`. Subscribes to `SCREEN_REQUESTED` from the bus. Exposes `key_event(int)` and `key_released(int)` pyqtSignals for direct keyboard wiring in `main.py`.
- `base/screen.py`: `Screen (QWidget)` — base class. Provides `_subscribe(event_type, callback)` for tracked bus subscriptions; `on_deactivated()` auto-unsubscribes all.
- `home/screen.py`: `HomeScreen` — vertical menu. `↑`/`↓` to navigate, `Enter` publishes `ScreenRequestedEvent` to bus.
- `dashboard/screen.py`: `DashboardScreen` — full-screen numeric grid + graphs. Subscribes to `SIGNALS_RECEIVED` and `ALARM_FIRED` via bus in `on_activated()`; unsubscribes in `on_deactivated()`.
- `ve_calibration/screen.py`: `VeCalibrationScreen` — 16×16 VE map table + heatmap + top-bar signal cells. `↑`/`↓` edits VE; `G` opens `PercentageDialog` to apply a % increment to cursor cells; `R` resets. Calls `_writer.on_adjustment_made()` directly on adjustment.
- `ve_calibration/ve_map_state.py`: `VeMapState` — in-memory 16×16 VE map. Computes bilinear interpolation weights, tracks modified cells. `adjust_ve(rpm, map, delta)` adds a fixed delta weighted by interpolation; `adjust_ve_by_percentage(rpm, map, pct)` multiplies each cursor cell by `(1 + pct/100)`. Module-level singleton `ve_map_state`.
- `ve_calibration/ve_write_controller.py`: `VeWriteController` — 1-second debounce; sends modified rows directly via `get_ecu_connection().send_command()`.
- `ve_calibration/percentage_dialog.py`: `PercentageDialog` — `QDialog` modal com tema escuro. Apresenta um `QLineEdit` com `QDoubleValidator` (−100 a 100). Enter confirma, ESC cancela. Expõe `value() -> float`.
- `components/signal_card.py`: `SignalCard` — reusable Qt widget for a labeled numeric value.

**`app/alarm/`** — Limit alarms
- `processor.py`: `AlarmProcessor (QThread)` — subscribes to `SIGNALS_RECEIVED` via bus. For each signal, publishes one `AlarmFiredEvent(signal, until)` per alarm period and only re-publishes after `until` expires. Audio loop polls `vehicle_state.is_any_alarm_firing()` every 100 ms and dispatches play/stop via `QueuedConnection`.

**`app/event/`** — Event types, bus, and keyboard-triggered actions
- `app_events.py`: `AppEventType` enum + frozen dataclass per event type.
- `bus.py`: `EventBus` singleton (`event_bus`). One `pyqtSignal(object)` per type; `publish()` / `subscribe()` / `unsubscribe()` API.
- `marker.py`: `EventMarker (QObject)` — filters `Key_Return`/`Key_Enter`, plays a one-shot beep, publishes `EventMarkRequestedEvent` to bus.
- `key_hold_detector.py`: `KeyHoldDetector (QObject)` — generic hold detector. Emits `triggered` after a key is held for the configured duration. Auto-repeat safe.
- `lambda_toggle.py`: `LambdaToggle (QObject)` — reads `vehicle_state.is_lambda_loop_closed()`, plays a sound, publishes `EcuCommandRequestedEvent` to bus.

**`app/log_writer/`** — CSV logging
- `log_writer.py`: `LogWriter (QObject)` owns a `Worker` moved to a dedicated `QThread`. CSV columns: `Timestamp; Event; <ECU fields...>`. `set_event_pending()` marks the next row with `"MARK"`.

**`app/config.py`** — Configuration
- Loads `config.json` on import and exposes a module-level `config: AppConfig` instance.

**`app/logger.py`** — Logging setup
- `setup_logging()`: configures `logging.basicConfig`. Called once at the top of `main()`.

## Adding or modifying signals

1. Add/edit an entry in the `Signal` enum in `app/masterinjection/signal.py`.
2. Add it to `config.json` under `dashboard.grid` and/or `dashboard.graph`.

For calculated signals, set `"calculated": True` and provide a `"value"` lambda over `parsed_data`. Order in the enum matters — calculated signals must come after all their dependencies.

## Adding a new app-level event

1. Add a value to `AppEventType` in `app/event/app_events.py`.
2. Add a frozen dataclass subclassing `AppEvent` with the event's fields.
3. Add a `pyqtSignal(object)` attribute to `_EventBusQObject` and an entry in `_SIGNAL_ATTR` in `app/event/bus.py`.
4. Publisher calls `event_bus.publish(MyEvent(...))`.
5. Subscriber calls `event_bus.subscribe(AppEventType.MY_EVENT, callback)`.

## Adding keyboard-triggered actions

- **Instant actions** (single key press): override `keyPressEvent` in the target `Screen` subclass and filter by key code.
- **Hold actions** (key held N seconds): create `KeyHoldDetector(key, hold_ms)`, connect `AppWindow.key_event` → `on_key_pressed` and `AppWindow.key_released` → `on_key_released`, then connect `triggered` to your action handler. Wire in `main.py`.

Keyboard events are wired **directly** in `main.py` — they do not go through the bus.

## Sending commands to the ECU

Call `get_ecu_connection().send_command(cmd: EcuCommand)` from any thread — it's queued internally and sent after the next complete frame. Add new commands to `EcuCommand` in `app/masterinjection/protocol.py`.

## ECU serial protocol

The ECU streams two frame types per cycle:
- `#D01;val1;val2;...` — primary sensor data
- `#D02;val1;val2;...` — secondary sensor data

`EcuConnectionSerial` waits for one of each, joins them with `;`, and emits the combined string. `SignalProcessor` accesses fields by absolute index across this combined string. Only `#D01`-prefixed lines are logged to CSV.
