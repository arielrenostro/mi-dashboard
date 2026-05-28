## ADDED Requirements

### Requirement: Inbound ECU data flows through a defined pipeline
The system SHALL process inbound data in this sequence:
1. `EcuConnection.emitter(str)` → `SignalProcessor.process_line()` (parse signals)
2. `EcuConnection.emitter(str)` → `LogWriter.write()` (raw line, unmodified)
3. `SignalProcessor` → bus `SIGNALS_RECEIVED` → `AlarmProcessor.process_signals()`
4. `SignalProcessor` → bus `SIGNALS_RECEIVED` → `VehicleState.update()`
5. `SignalProcessor` → bus `SIGNALS_RECEIVED` → `DashboardScreen.on_signal_received()` (when active)
6. `AlarmProcessor` → bus `ALARM_FIRED` → `DashboardScreen.fire_field_alarm()` (when active)
7. `VeCalibrationScreen` reads `vehicle_state` via a 100 ms `QTimer` (when active)

#### Scenario: Raw line is logged without parsing
- **WHEN** a raw frame line is emitted by `EcuConnection`
- **THEN** `LogWriter.write()` SHALL receive the unmodified string

#### Scenario: Parsed signals are broadcast on bus
- **WHEN** `SignalProcessor` finishes processing a frame
- **THEN** `SIGNALS_RECEIVED` SHALL be published on the event bus

### Requirement: Outbound commands flow from keyboard to ECU
The system SHALL dispatch outbound ECU commands via this pipeline:
1. `AppWindow.key_event(int)` → `EventMarker.handle_key()` → bus `EVENT_MARK_REQUESTED` → `LogWriter.set_event_pending()`
2. `AppWindow.key_event(int)` → `KeyHoldDetector.on_key_pressed()`; `AppWindow.key_released(int)` → `on_key_released()`
3. `KeyHoldDetector.triggered` → `LambdaToggle.handle_trigger()` → bus `ECU_COMMAND_REQUESTED` → `EcuConnection.send_command()`
4. `VeCalibrationScreen` → direct call `VeWriteController.on_adjustment_made()` → (1 s debounce) → `EcuConnection.send_command(cmd, values)`

#### Scenario: Lambda toggle reaches ECU
- **WHEN** Space is held for 2 s
- **THEN** an `EcuCommandRequestedEvent` SHALL be published and `EcuConnection.send_command()` SHALL be called with the appropriate lambda loop command

### Requirement: No UI calls are made from background threads
All UI updates MUST go through `pyqtSignal` / `@Slot` or the event bus. Qt delivers cross-thread signals via `QueuedConnection` automatically. `QMediaPlayer` MUST be called only from its owner (main) thread.

#### Scenario: ECU reader does not update UI directly
- **WHEN** a new frame is received on the ECU reader thread
- **THEN** any UI update SHALL happen via a queued signal or bus event dispatched on the main thread

### Requirement: VehicleState is the only shared mutable state
`VehicleState` MUST protect all access with `threading.RLock`. `EcuConnection.send_command()` MUST use an internal `queue.Queue` for thread safety.

#### Scenario: Concurrent access to VehicleState is safe
- **WHEN** the alarm poller reads `is_any_alarm_firing()` concurrently with the ECU reader calling `update()`
- **THEN** no race condition or data corruption SHALL occur

### Requirement: Lambda loop state is filtered for deceleration transients
The effective lambda loop state stored in `VehicleState` MUST be computed by `LambdaLoopStateProcessor` using these rules:
- ECU reports Closed (1): effective = Closed (always authoritative)
- ECU reports Open (0) AND (PEDAL > 0 OR MAP > 20 kPa): effective = unchanged (hold previous)
- ECU reports Open (0) AND PEDAL == 0 AND MAP ≤ 20 kPa: effective = Open

When a toggle command is dispatched via `ECU_COMMAND_REQUESTED`, `LambdaLoopStateProcessor` MUST update `VehicleState` immediately without waiting for ECU confirmation.

#### Scenario: Transient open during deceleration is ignored
- **WHEN** the ECU reports Open and PEDAL == 0 and MAP == 15 kPa (below 20 kPa threshold)
- **THEN** effective lambda loop state SHALL be Open

#### Scenario: Open during fuel cut is held as previous state
- **WHEN** the ECU reports Open and PEDAL == 0 and MAP == 50 kPa (above threshold)
- **THEN** effective lambda loop state SHALL remain unchanged from the previous value

### Requirement: Application startup follows a defined sequence
The system SHALL initialize components in this order:
1. `setup_logging()`
2. `QApplication` created
3. `LogWriter` instantiated
4. `AlarmProcessor` instantiated and started (subscribes to `SIGNALS_RECEIVED`)
5. `SignalProcessor` instantiated
6. Bus subscriptions wired: `SIGNALS_RECEIVED → vehicle_state.update`, `ECU_COMMAND_REQUESTED → ecu_connection.send_command`, `EVENT_MARK_REQUESTED → log_writer.set_event_pending`
7. ECU connection chosen and registered
8. `AppWindow` created (subscribes to `SCREEN_REQUESTED`)
9. Keyboard handlers wired
10. `EcuConnection.emitter` connected to `SignalProcessor.process_line` and `LogWriter.write`
11. `EcuConnectionThread.start()`
12. `app.exec()` — Qt event loop
13. On exit: `AppWindow.close()`, `AlarmProcessor.stop()`, `EcuConnectionThread.stop()`

#### Scenario: ECU thread starts after all subscribers are wired
- **WHEN** the application starts
- **THEN** `EcuConnectionThread.start()` SHALL be called only after all bus subscriptions and signal connections are established
