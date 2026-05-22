# Spec: Data Pipeline

Describes the full data flow from ECU to display, storage, and commands.

Implementation: `main.py` (wiring), `app/` (all modules).

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
3.  AppWindow created (full-screen, QStackedWidget)
4.  Dashboard, VeCalibrationScreen, HomeScreen instantiated
5.  VeCalibrationScreen populated with default VE map axes
6.  Screens registered: "home", "dashboard", "ve_calibration"
7.  HomeScreen.screen_requested connected to AppWindow.show_screen
8.  LogWriter, AlarmProcessor instantiated and connected
9.  EcuConnection or EcuConnectionMock chosen based on MOCK_FILE
10. LambdaLoopStateProcessor, LambdaToggle, KeyHoldDetector, EventMarker instantiated and connected
11. VeWriteController instantiated and connected to VeCalibrationScreen + EcuConnection
12. SignalProcessor instantiated and connected to all consumers (Dashboard, AlarmProcessor, VehicleState, LambdaLoopStateProcessor, VeCalibrationScreen)
13. EcuConnection.emitter connected to SignalProcessor and LogWriter
14. AlarmProcessor.start(), EcuConnection.start()
15. AppWindow.show()  ← displays HomeScreen
16. app.exec()  ← Qt event loop runs until window is closed
17. app_window.close(), alarm_processor.stop(), ecu_connection.stop()
```
