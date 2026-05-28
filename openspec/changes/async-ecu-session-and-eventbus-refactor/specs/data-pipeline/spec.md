## MODIFIED Requirements

### Requirement: Inbound ECU data flows through the bus exclusively
The system SHALL process inbound data exclusively via the event bus. No direct signal connections between `EcuSession` and `SignalProcessor` or `LogWriter` are permitted. The pipeline is:
1. `EcuSession` I/O thread → bus `ECU_MESS_FRAME` (per frame, queued to main thread)
2. `SignalProcessor` subscribes to `ECU_MESS_FRAME` → processes signals → publishes `SIGNALS_RECEIVED`
3. `LogWriter` subscribes to `ECU_MESS_FRAME` → accumulates `#D01`+`#D02` → writes CSV row
4. `AlarmProcessor` subscribes to `SIGNALS_RECEIVED` → checks limits → updates `VehicleState` → publishes `ALARM_FIRED`
5. `VehicleState` subscribes to `SIGNALS_RECEIVED` → updates signal snapshot
6. `DashboardScreen` subscribes to `SIGNALS_RECEIVED` and `ALARM_FIRED` (when active)
7. `VeCalibrationScreen` reads `vehicle_state` via 100 ms `QTimer` (when active)

#### Scenario: SignalProcessor receives frames via bus
- **WHEN** `ECU_MESS_FRAME` is published for a `#D01` line
- **THEN** `SignalProcessor` SHALL process the signals in that frame and publish `SIGNALS_RECEIVED`

#### Scenario: No direct emitter connections between session and processors
- **WHEN** `EcuSession` publishes a frame
- **THEN** the frame MUST reach `SignalProcessor` and `LogWriter` only via the bus, not via a direct pyqtSignal connection

### Requirement: SignalProcessor processes frames individually and allows partial signal sets
`SignalProcessor` SHALL subscribe to `ECU_MESS_FRAME` on the bus. For each frame received, it SHALL parse only the signals whose indices fall within that frame type. It SHALL publish `SIGNALS_RECEIVED` with a partial dict containing only the signals parsed from that frame. Callers MUST handle partial dicts.

#### Scenario: D01 frame produces partial SIGNALS_RECEIVED
- **WHEN** `ECU_MESS_FRAME` with `frame_type="D01"` is received
- **THEN** `SIGNALS_RECEIVED` SHALL be published containing only signals indexed in the D01 range

#### Scenario: D02 frame produces its own SIGNALS_RECEIVED
- **WHEN** `ECU_MESS_FRAME` with `frame_type="D02"` is received
- **THEN** `SIGNALS_RECEIVED` SHALL be published containing only signals indexed in the D02 range

### Requirement: Outbound commands flow from keyboard to ECU via bus
The system SHALL dispatch outbound ECU commands via this pipeline:
1. `AppWindow.key_event(int)` → `EventMarker.handle_key()` → bus `EVENT_MARK_REQUESTED` → `LogWriter.set_event_pending()`
2. `AppWindow.key_event(int)` → `KeyHoldDetector.on_key_pressed()`; `AppWindow.key_released(int)` → `on_key_released()`
3. `KeyHoldDetector.triggered` → `LambdaToggle.handle_trigger()` → bus `ECU_COMMAND_REQUESTED` → `EcuSession.send_command()`
4. `VeCalibrationScreen` → bus `ECU_COMMAND_REQUESTED` (with VE row data) → `VeWriteController` (1 s debounce) → `EcuSession.set_ve_row()`

Screens MUST NOT call `get_ecu_session().send_command()` directly. All outbound ECU interactions MUST be mediated via `ECU_COMMAND_REQUESTED` on the bus.

#### Scenario: VE adjustment triggers ECU command via bus
- **WHEN** the user adjusts a VE cell in `VeCalibrationScreen`
- **THEN** an `ECU_COMMAND_REQUESTED` event SHALL be published on the bus, not a direct call to the session

#### Scenario: Lambda toggle reaches ECU via bus
- **WHEN** Space is held for 2 s
- **THEN** an `EcuCommandRequestedEvent` SHALL be published on the bus and `EcuSession` SHALL execute the appropriate command

### Requirement: All inter-component events pass through the bus
All communication between non-UI components (session, processors, state, log writer) MUST use the event bus. UI components (screens) MUST subscribe to bus events for data and publish bus events for actions that affect other layers.

#### Scenario: UI-local events stay local
- **WHEN** a screen changes its internal visual state (e.g., heatmap cell highlight)
- **THEN** no bus event SHALL be published for that internal UI change

#### Scenario: UI actions that affect shared state use the bus
- **WHEN** a screen triggers a VE adjustment that must be written to the ECU
- **THEN** the action SHALL be published as an `ECU_COMMAND_REQUESTED` event on the bus

### Requirement: Application startup initializes session before subscribers
The system SHALL initialize components in this order:
1. `setup_logging()`
2. `QApplication` created
3. `LogWriter` instantiated (subscribes to `ECU_MESS_FRAME`)
4. `AlarmProcessor` instantiated (subscribes to `SIGNALS_RECEIVED`)
5. `SignalProcessor` instantiated (subscribes to `ECU_MESS_FRAME`)
6. `VehicleState` subscriptions wired (`SIGNALS_RECEIVED` → `vehicle_state.update_signals`)
7. `EcuSession` instantiated and registered; `ECU_COMMAND_REQUESTED` → `session.send_command` wired
8. `AppWindow` created (subscribes to `SCREEN_REQUESTED`)
9. Keyboard handlers wired
10. `session.start()` — starts I/O thread
11. `app.exec()` — Qt event loop
12. On exit: `AppWindow.close()`, `AlarmProcessor cleanup`, `session.stop()`

#### Scenario: Session starts after all subscribers are registered
- **WHEN** the application starts
- **THEN** `session.start()` SHALL be called only after all bus subscriptions are established

## REMOVED Requirements

### Requirement: Inbound ECU data flows through a defined pipeline (old)
**Reason**: Replaced by the bus-exclusive pipeline above. The `EcuConnection.emitter(str)` direct connections to `SignalProcessor.process_line()` and `LogWriter.write()` are removed.
**Migration**: Both `SignalProcessor` and `LogWriter` MUST subscribe to `ECU_MESS_FRAME` on the bus.
