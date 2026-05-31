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

#### Scenario: SignalProcessor handles each frame type independently and immediately
- **WHEN** `EcuFrameReceivedEvent(frame_type=D01, values=[...])` is published
- **THEN** `SignalProcessor` SHALL compute and publish `SignalsReceivedEvent` with D01 signals immediately, without waiting for D02

#### Scenario: SignalsReceivedEvent carries a timestamp
- **WHEN** `SignalProcessor` publishes `SignalsReceivedEvent`
- **THEN** the event SHALL include a `timestamp: float` field set to `time.monotonic()` at publish time

#### Scenario: SignalProcessor does not use direct Qt signal from connection thread
- **WHEN** the application is running
- **THEN** `SignalProcessor` SHALL receive frames only via `EcuFrameReceivedEvent` bus subscription
