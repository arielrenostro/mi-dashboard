## MODIFIED Requirements

### Requirement: AlarmProcessor detects out-of-range signals and updates VehicleState
On each `SIGNALS_RECEIVED` event, `AlarmProcessor` MUST check every alarm-enabled signal against its `[alarm_min, alarm_max]` range. It SHALL call `vehicle_state.set_alarm(signal, in_alarm: bool)` for each signal to update the centralized alarm state. When a signal enters alarm and the cooldown window has expired (or it is the first occurrence), the processor MUST publish `AlarmFiredEvent(signal, until=now + duration_s)`.

#### Scenario: VehicleState is updated on each signal check
- **WHEN** `SIGNALS_RECEIVED` arrives with CLT out of range
- **THEN** `vehicle_state.set_alarm(CLT, True)` SHALL be called

#### Scenario: VehicleState is cleared when signal returns to range
- **WHEN** CLT returns to a valid range
- **THEN** `vehicle_state.set_alarm(CLT, False)` SHALL be called

#### Scenario: AlarmFiredEvent is published on leading edge
- **WHEN** a signal value is out of range and no cooldown is active
- **THEN** `AlarmFiredEvent` SHALL be published with `until = now + duration_s`

#### Scenario: AlarmFiredEvent is not re-published during cooldown
- **WHEN** a signal stays out of range and `now < _alarm_until[signal]`
- **THEN** no new `AlarmFiredEvent` SHALL be published

#### Scenario: Cooldown resets when alarm clears
- **WHEN** a signal returns to range before `until` expires
- **THEN** `_alarm_until[signal]` SHALL be removed so the next occurrence starts a fresh window

### Requirement: Alarm audio is driven by state transitions, not a polling thread
`AlarmProcessor` MUST NOT run a dedicated polling thread. Instead, after each `vehicle_state.set_alarm()` call, it SHALL check `vehicle_state.is_any_alarm_firing()`. If the overall alarm state changed (off → on or on → off), it SHALL dispatch audio play or stop via `Qt.ConnectionType.QueuedConnection` to the main thread.

#### Scenario: Audio starts when first alarm begins
- **WHEN** no alarm was active and a signal enters alarm
- **THEN** `alarm.wav` SHALL start playing on the main thread via queued dispatch

#### Scenario: Audio stops when all alarms clear
- **WHEN** all alarm conditions have ended (no signal in alarm)
- **THEN** playback SHALL stop via queued dispatch

#### Scenario: No extra thread is created for audio polling
- **WHEN** `AlarmProcessor` is instantiated
- **THEN** no additional thread beyond those managed by Qt SHALL be created

### Requirement: Audio restarts when track ends during active alarm
`AlarmProcessor` SHALL connect to `QMediaPlayer.mediaStatusChanged`. When `EndOfMedia` is received and `vehicle_state.is_any_alarm_firing()` returns True, it SHALL restart playback from the beginning.

#### Scenario: Audio restarts when track ends during active alarm
- **WHEN** `alarm.wav` track ends and an alarm is still firing
- **THEN** playback SHALL restart from the beginning

#### Scenario: Audio does not restart when alarm cleared before track ends
- **WHEN** `alarm.wav` track ends and no alarm is firing
- **THEN** playback SHALL NOT restart

### Requirement: QMediaPlayer calls are dispatched to the main thread
All `QMediaPlayer.play()` and `QMediaPlayer.stop()` calls MUST be dispatched via `Qt.ConnectionType.QueuedConnection` to respect `QMediaPlayer` thread affinity.

#### Scenario: Play is dispatched via queued connection
- **WHEN** alarm state changes to active from a non-main-thread context
- **THEN** the actual `play()` call SHALL execute on the main Qt thread

### Requirement: Dashboard cell flashes while alarm is firing
When `DashboardScreen` receives `AlarmFiredEvent`, it MUST flash the corresponding grid cell. Flash pattern: cell background alternates black/yellow every 200 ms; text label color is set to red. Flashing continues as long as `vehicle_state.is_alarm_firing(signal)` returns True.

#### Scenario: Cell flashes on alarm
- **WHEN** `AlarmFiredEvent` is received for a signal
- **THEN** the corresponding grid cell SHALL alternate black/yellow background at 200 ms intervals with red text

#### Scenario: Cell restores on alarm end
- **WHEN** the alarm condition clears
- **THEN** the cell background SHALL restore to black and the next value update SHALL restore normal text color

## REMOVED Requirements

### Requirement: Alarm audio plays while any alarm is firing (polling version)
**Reason**: Polling loop replaced by state-transition-driven audio dispatch. `AlarmProcessor` no longer owns a polling thread or loop.
**Migration**: Audio is now triggered by `set_alarm()` transitions. The `is_any_alarm_firing()` check is inline after each alarm update, not in a separate thread.
