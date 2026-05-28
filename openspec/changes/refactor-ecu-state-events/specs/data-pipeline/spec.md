## MODIFIED Requirements

### Requirement: Inbound ECU data flows through a defined pipeline
The system SHALL process inbound data in this sequence:
1. `EcuProtocol` read loop → bus `ECU_FRAME_RECEIVED` → `SignalProcessor` (parse signals by frame type)
2. `EcuProtocol` read loop → bus `ECU_FRAME_RECEIVED` → `LogWriter.write()` (D01 frames only, reconstructed)
3. `EcuProtocol` named method → bus `ECU_RESPONSE_RECEIVED` → `VehicleState._on_ecu_response()`
4. `SignalProcessor` → bus `SIGNALS_RECEIVED` → `AlarmProcessor.process_signals()`
5. `SignalProcessor` → bus `SIGNALS_RECEIVED` → `DashboardScreen.on_signal_received()` (when active)
6. `AlarmProcessor` → bus `ALARM_FIRED` → `DashboardScreen.fire_field_alarm()` (when active)
7. `VeCalibrationScreen` reads `vehicle_state` via a 100 ms `QTimer` OR subscribes to `SIGNALS_RECEIVED` (when active)

#### Scenario: D01 frame is logged without parsing
- **WHEN** `EcuFrameReceivedEvent(frame_type=D01, values=[...])` is published
- **THEN** `LogWriter` SHALL reconstruct and write the raw D01 line to CSV

#### Scenario: D02 frame is not logged
- **WHEN** `EcuFrameReceivedEvent(frame_type=D02, values=[...])` is published
- **THEN** `LogWriter` SHALL NOT write anything — only D01 frames are logged

#### Scenario: SignalProcessor handles each frame type independently
- **WHEN** `EcuFrameReceivedEvent(frame_type=D01, values=[...])` is published
- **THEN** `SignalProcessor` SHALL compute and publish signals whose `Signal.frame == D01` immediately, without waiting for D02

#### Scenario: SignalProcessor does not use direct Qt signal from connection thread
- **WHEN** the application is running
- **THEN** `SignalProcessor` SHALL receive frames only via `EcuFrameReceivedEvent` bus subscription

### Requirement: Outbound commands flow to ECU exclusively via VehicleState
The system SHALL dispatch outbound ECU commands via this pipeline:
1. `AppWindow.key_event(int)` → `EventMarker.handle_key()` → bus `EVENT_MARK_REQUESTED` → `LogWriter.set_event_pending()`
2. `AppWindow.key_event(int)` → `KeyHoldDetector.on_key_pressed()`; `AppWindow.key_released(int)` → `on_key_released()`
3. `KeyHoldDetector.triggered` → `LambdaToggle.handle_trigger()` → `vehicle_state.open_lambda_loop()` or `close_lambda_loop()`
4. `VeCalibrationScreen` → direct call `VeWriteController.on_adjustment_made()` → (1 s debounce) → `vehicle_state.write_ve_row(idx, data)`
5. `VehicleState` → `EcuProtocol.open_lambda_loop()` / `set_ve_row()` / etc.

#### Scenario: Lambda toggle reaches ECU via VehicleState and EcuProtocol
- **WHEN** Space is held for 2 s
- **THEN** `LambdaToggle` SHALL call `vehicle_state.open_lambda_loop()`, which SHALL call `protocol.open_lambda_loop()`, which SHALL send the command and return `LambdaResponse`

#### Scenario: VE write reaches ECU via VehicleState, not direct protocol call
- **WHEN** `VeWriteController` debounce fires
- **THEN** it SHALL call `vehicle_state.write_ve_row(idx, data)` — never `get_ecu_protocol().set_ve_row()` directly

### Requirement: Screen navigation uses pyqtSignal, not EventBus
`Screen` base class SHALL expose `screen_requested = pyqtSignal(str)`. Screens emit this signal for navigation. `AppWindow` SHALL connect each registered screen's `screen_requested` to `show_screen()`.

#### Scenario: HomeScreen navigates without EventBus
- **WHEN** the user presses Enter on a menu item in `HomeScreen`
- **THEN** `HomeScreen` SHALL emit `self.screen_requested.emit(screen_name)` — never `event_bus.publish(ScreenRequestedEvent(...))`

#### Scenario: AppWindow connects screen signal on registration
- **WHEN** a screen is registered in `AppWindow`
- **THEN** `AppWindow` SHALL connect `screen.screen_requested` to `self.show_screen`

### Requirement: Application startup follows a defined sequence
The system SHALL initialize components in this order:
1. `setup_logging()`
2. `QApplication` created
3. `EcuTransport` instantiated (serial or mock per config)
4. `EcuProtocol` instantiated with the transport
5. `EcuConnectionThread` instantiated with the protocol
6. `LogWriter` instantiated; subscribes to `ECU_FRAME_RECEIVED` on bus
7. `AlarmProcessor` instantiated and started; subscribes to `SIGNALS_RECEIVED`
8. `SignalProcessor` instantiated; subscribes to `ECU_FRAME_RECEIVED` on bus
9. `VehicleState` subscribes to `ECU_FRAME_RECEIVED`, `ECU_RESPONSE_RECEIVED`, `ECU_HANDSHAKE_COMPLETED` on bus
10. ECU protocol registered in registry
11. `AppWindow` created; connects `screen_requested` signals (no bus subscription for screen navigation)
12. Keyboard handlers wired
13. `EcuConnectionThread.start()`
14. `app.exec()` — Qt event loop
15. On exit: `AppWindow.close()`, `AlarmProcessor.stop()`, `EcuConnectionThread.stop()`

#### Scenario: ECU thread starts after all bus subscribers are wired
- **WHEN** the application starts
- **THEN** `EcuConnectionThread.start()` SHALL be called only after steps 6–10 are complete

#### Scenario: No emitter(str) or ScreenRequestedEvent wiring in main.py
- **WHEN** the application starts
- **THEN** `main.py` SHALL NOT connect any `emitter` signal nor subscribe to `SCREEN_REQUESTED` on the bus
