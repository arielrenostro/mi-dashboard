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
               │  emitter(dict) ─────┼──── (legacy, kept for compat)
               │  + bus SIGNALS_RECEIVED   (all consumers use bus)
               └─────────────────────┘
                          │
        ┌─────────────────┼──────────────────────────┐
        ▼                 ▼                           ▼
AlarmProcessor       VehicleState           DashboardScreen
process_signals()    update()               on_signal_received()
(via bus subscriber) (via bus subscriber)   (subscribed in on_activated())

  LogWriter.write(str)  ◄──── EcuConnection.emitter  (raw line, not parsed)

event_bus → ALARM_FIRED
  └──► DashboardScreen.fire_field_alarm()  (subscribed in on_activated())

  VeCalibrationScreen._highlight_timer (100 ms)
      └── reads vehicle_state.get(RPM/MAP)
      └── ve_map_state.calculate_interpolation_weights()
      └── highlight_interpolation() + mark_modified_cells() + update_heatmap()
      └── _update_top_bar()

  VeCalibrationScreen._adjust_ve() / reset
      └── direct call: self._writer.on_adjustment_made()
              └── (after 1 s debounce) get_ecu_connection().send_command(VE_ROW_N, values)
```

---

## Signal flow: inbound (ECU → UI)

| Step | Producer | Mechanism | Consumer |
|---|---|---|---|
| 1 | `EcuConnection` | `emitter(str)` pyqtSignal | `SignalProcessor.process_line()` |
| 2 | `EcuConnection` | `emitter(str)` pyqtSignal | `LogWriter.write()` (raw line) |
| 3 | `SignalProcessor` | bus `SIGNALS_RECEIVED` | `AlarmProcessor.process_signals()` |
| 4 | `SignalProcessor` | bus `SIGNALS_RECEIVED` | `VehicleState.update()` |
| 5 | `SignalProcessor` | bus `SIGNALS_RECEIVED` | `DashboardScreen.on_signal_received()` (when active) |
| 6 | `AlarmProcessor` | bus `ALARM_FIRED` | `DashboardScreen.fire_field_alarm()` (when active) |
| 7 | `VeCalibrationScreen` | 100 ms `QTimer` | reads `vehicle_state` directly |

---

## Signal flow: outbound (keyboard → ECU)

| Step | Producer | Mechanism | Consumer |
|---|---|---|---|
| 1 | `AppWindow` | `key_event(int)` pyqtSignal | `EventMarker.handle_key()` |
| 2 | `AppWindow` | `key_event(int)` pyqtSignal | `KeyHoldDetector.on_key_pressed()` |
| 3 | `AppWindow` | `key_released(int)` pyqtSignal | `KeyHoldDetector.on_key_released()` |
| 4 | `KeyHoldDetector` | `triggered()` pyqtSignal | `LambdaToggle.handle_trigger()` |
| 5 | `LambdaToggle` | bus `ECU_COMMAND_REQUESTED` | `EcuConnection.send_command()` |
| 6 | `EventMarker` | bus `EVENT_MARK_REQUESTED` | `LogWriter.set_event_pending()` |
| 7 | `VeCalibrationScreen` | direct call | `VeWriteController.on_adjustment_made()` |
| 8 | `VeWriteController` | `get_ecu_connection().send_command()` | ECU (after 1 s debounce) |

---

## Threading model

| Thread | Owner object | Responsibility |
|---|---|---|
| Main (Qt event loop) | `QApplication` | UI rendering, slot dispatch, `QMediaPlayer` |
| ECU reader | `EcuConnection` / `EcuConnectionMock` | Blocking serial I/O or CSV replay |
| Alarm poller | `AlarmProcessor` | 100 ms polling loop for audio control |
| Log writer | `LogWriter` internal `QThread` | Disk I/O (CSV append) |

### Thread safety rules

- **No UI calls from background threads.** All UI updates go through `pyqtSignal` / `@Slot` or the event bus — Qt delivers cross-thread signals via `QueuedConnection` automatically.
- **`QMediaPlayer` must be called from its owner thread (main).** `AlarmProcessor` uses `Qt.ConnectionType.QueuedConnection` for `_play_requested` and `_stop_requested`.
- **`VehicleState`** is the only shared mutable state accessible from multiple threads. All access is protected by `threading.RLock`.
- **`EcuConnection.send_command()`** is thread-safe: it uses a `queue.Queue` internally.
- **`event_bus.publish()`** is thread-safe: `pyqtSignal.emit()` is re-entrant; cross-thread delivery is automatic.

---

## Lambda Loop State

The effective lambda loop state (stored in `VehicleState`) is not simply the raw ECU value. It is filtered by `LambdaLoopStateProcessor`:

| ECU reports | Condition | Effective state | Reason |
|---|---|---|---|
| Closed (1) | any | Closed | ECU confirmation is always authoritative |
| Open (0) | PEDAL > 0 OR MAP > 20 kPa | Unchanged (keep previous) | Transient open during deceleration fuel cut |
| Open (0) | PEDAL == 0 AND MAP ≤ 20 kPa | Open | Genuine open-loop condition |

**Deceleration threshold:** `MAP ≤ 20 kPa`. During engine braking (foot off pedal, MAP drops to atmospheric), the ECU temporarily opens the lambda loop due to fuel cut. The filter holds the previous state until actual open-loop conditions are confirmed.

When a toggle command is dispatched via `ECU_COMMAND_REQUESTED`, `LambdaLoopStateProcessor.on_command_received()` updates `VehicleState` immediately, so the UI responds instantly without waiting for ECU confirmation.

---

## Startup sequence

```
1.  setup_logging()
2.  QApplication created
3.  LogWriter instantiated
4.  AlarmProcessor instantiated:
      - subscribes to SIGNALS_RECEIVED on event_bus internally
      - alarm_processor.start()
5.  SignalProcessor instantiated
6.  Bus subscriptions in main.py:
      event_bus.subscribe(SIGNALS_RECEIVED, vehicle_state.update)
      event_bus.subscribe(ECU_COMMAND_REQUESTED, ecu_connection.send_command)
      event_bus.subscribe(EVENT_MARK_REQUESTED, log_writer.set_event_pending)
7.  EcuConnectionSerial or EcuConnectionMock chosen; registered via register_ecu_connection()
8.  AppWindow created (full-screen, QStackedWidget):
      - subscribes to SCREEN_REQUESTED on event_bus
      - _register_screens():
          a. HomeScreen instantiated (publishes SCREEN_REQUESTED on Enter)
          b. VeCalibrationScreen instantiated (owns VeWriteController directly)
          c. DashboardScreen instantiated (subscribes SIGNALS_RECEIVED + ALARM_FIRED in on_activated)
          d. Screens added to QStackedWidget; show_screen("home") called
9.  Keyboard handlers wired (EventMarker, KeyHoldDetector, LambdaToggle)
10. EcuConnection.emitter connected to SignalProcessor.process_line and LogWriter.write
11. EcuConnectionThread.start()
12. app.exec()  ← Qt event loop
13. app_window.close(), alarm_processor.stop(), ecu_connection_thread.stop()
```
