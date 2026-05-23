# Spec: Data Pipeline

Describes the full data flow from ECU to display, storage, and commands.

Implementation: `main.py` (top-level wiring), `app/ui/window.py` (screen wiring), `app/` (all modules).

---

## Component diagram

```
┌─────────────────────────────────────────────────────────┐
│ ECU thread                                              │
│  EcuConnection / EcuConnectionMock (QThread)           │
│      emitter(str) ─────────────────────────────────┐   │
└────────────────────────────────────────────────────│───┘
                                                     │ joined frame "#D01;...;#D02;..."
                          ┌──────────────────────────┘
                          │
               ┌──────────▼──────────┐
               │  SignalProcessor    │  (main thread, QObject)
               │  process_line(str)  │
               │  emitter(dict) ─────┼───────────────────────────────────────┐
               └─────────────────────┘                                       │
                                                                             │ parsed_data
          ┌──────────────────────────────────────────────────────────────────┤
          │                     │                     │                      │                      │
          ▼                     ▼                     ▼                      ▼                      ▼
  Dashboard             AlarmProcessor         VehicleState       LambdaLoopStateProcessor  VeCalibrationScreen
  process_signals()     process_signals()      update()           process_signals()          process_signals()
  (UI update)           (alarm check)          (shared state)     (effective loop state)     (top bar update)

  LogWriter.write(str)  ◄──── EcuConnection.emitter (raw line, not parsed)

  VeCalibrationScreen._highlight_timer (100 ms)
      └── reads vehicle_state.get(RPM/MAP)
      └── ve_map_state.calculate_interpolation_weights()
      └── highlight_interpolation() + mark_modified_cells() + update_heatmap()

  VeCalibrationScreen.ve_adjustment_made
      └── VeWriteController.on_adjustment_made()
              └── (after 1 s debounce) EcuConnection.send_command(WRITE_ON_MEMORY)
```

---

## Signal flow: inbound (ECU → UI)

| Step | Producer | Signal/call | Consumer |
|---|---|---|---|
| 1 | `EcuConnection` | `emitter(str)` | `SignalProcessor.process_line()` |
| 2 | `EcuConnection` | `emitter(str)` | `LogWriter.write()` (raw line) |
| 3 | `SignalProcessor` | `emitter(dict)` | `Dashboard.process_signals()` |
| 4 | `SignalProcessor` | `emitter(dict)` | `AlarmProcessor.process_signals()` |
| 5 | `SignalProcessor` | `emitter(dict)` | `VehicleState.update()` |
| 6 | `SignalProcessor` | `emitter(dict)` | `LambdaLoopStateProcessor.process_signals()` |
| 7 | `AlarmProcessor` | `emitter(Signal)` | `Dashboard.fire_field_alarm()` |
| 8 | `SignalProcessor` | `emitter(dict)` | `VeCalibrationScreen.process_signals()` |

---

## Signal flow: outbound (keyboard → ECU)

| Step | Producer | Signal/call | Consumer |
|---|---|---|---|
| 1 | `AppWindow` | `key_event(int)` | `EventMarker.handle_key()` |
| 2 | `AppWindow` | `key_event(int)` | `KeyHoldDetector.on_key_pressed()` |
| 3 | `AppWindow` | `key_released(int)` | `KeyHoldDetector.on_key_released()` |
| 4 | `AppWindow` | `key_event(int)` | `VeCalibrationScreen.handle_key()` |
| 5 | `KeyHoldDetector` | `triggered()` | `LambdaToggle.handle_trigger()` |
| 6 | `LambdaToggle` | `command_requested(EcuCommand)` | `EcuConnection.send_command()` |
| 7 | `LambdaToggle` | `command_requested(EcuCommand)` | `LambdaLoopStateProcessor.on_command_sent()` |
| 8 | `EventMarker` | `event_triggered()` | `LogWriter.set_event_pending()` |
| 9 | `VeCalibrationScreen` | `ve_adjustment_made()` | `VeWriteController.on_adjustment_made()` |
| 10 | `VeWriteController` | `command_requested(EcuCommand)` | `EcuConnection.send_command()` |

---

## Threading model

| Thread | Owner object | Responsibility |
|---|---|---|
| Main (Qt event loop) | `QApplication` | UI rendering, slot dispatch, `QMediaPlayer` |
| ECU reader | `EcuConnection` / `EcuConnectionMock` | Blocking serial I/O or CSV replay |
| Alarm poller | `AlarmProcessor` | 100 ms polling loop for audio control |
| Log writer | `LogWriter` internal `QThread` | Disk I/O (CSV append) |

### Thread safety rules

- **No UI calls from background threads.** All UI updates go through `pyqtSignal` / `@Slot`, which Qt dispatches on the correct thread.
- **`QMediaPlayer` must be called from its owner thread (main).** `AlarmProcessor` uses `Qt.ConnectionType.QueuedConnection` for `_play_requested` and `_stop_requested` to ensure this.
- **`VehicleState`** is the only shared mutable state accessible from multiple threads. All access is protected by `threading.RLock`.
- **`EcuConnection.send_command()`** is thread-safe: it uses a `queue.Queue` internally.

---

## Lambda Loop State

The effective lambda loop state (stored in `VehicleState`) is not simply the raw ECU value. It is filtered by `LambdaLoopStateProcessor`:

| ECU reports | Condition | Effective state | Reason |
|---|---|---|---|
| Closed (1) | any | Closed | ECU confirmation is always authoritative |
| Open (0) | PEDAL > 0 OR MAP > 20 kPa | Unchanged (keep previous) | Transient open during deceleration fuel cut |
| Open (0) | PEDAL == 0 AND MAP ≤ 20 kPa | Open | Genuine open-loop condition |

**Deceleration threshold:** `MAP ≤ 20 kPa` (constant `DECEL_MAP_THRESHOLD` in `app/vehicle/lambda_loop_state_processor.py`).

**Intent:** during engine braking (foot off pedal, MAP drops to atmospheric), the ECU temporarily opens the lambda loop due to fuel cut. Accepting this as a genuine state change would cause spurious toggle logic. The filter holds the previous state until actual open-loop conditions are confirmed.

When a toggle command is sent by the user, `LambdaLoopStateProcessor.on_command_sent()` updates `VehicleState` immediately without waiting for ECU confirmation, so the UI responds instantly.

---

## Startup sequence

```
1.  setup_logging()
2.  QApplication created
3.  LogWriter instantiated
4.  AlarmProcessor instantiated; alarm_processor.start()
5.  SignalProcessor instantiated; emitter connected to AlarmProcessor and VehicleState
6.  EcuConnectionSerial or EcuConnectionMock chosen based on config.connection.mock;
    registered via register_ecu_connection()
7.  AppWindow created (full-screen, QStackedWidget)
    └── _register_screens():
        a. HomeScreen instantiated; screen_requested connected to AppWindow.show_screen
        b. VeCalibrationScreen instantiated (owns VeWriteController internally)
        c. DashboardScreen instantiated; SignalProcessor.emitter connected to on_signal_received
        d. Screens added to QStackedWidget; show_screen("home") called
8.  EcuConnection.emitter connected to SignalProcessor.process_line and LogWriter.write
9.  EcuConnectionThread.start()
10. app.exec()  ← Qt event loop runs until window is closed
11. app_window.close(), alarm_processor.stop(), ecu_connection_thread.stop()

[pending — not yet wired]:
    LambdaLoopStateProcessor connected to SignalProcessor.emitter
    LambdaToggle + KeyHoldDetector instantiated and connected to AppWindow key events
    EventMarker instantiated and connected to AppWindow key event + LogWriter
    ECU startup commands: RPM_BREAKPOINTS, MAP_BREAKPOINTS, VE rows 0–15
```
