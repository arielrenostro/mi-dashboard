## ADDED Requirements

### Requirement: AlarmProcessor detects out-of-range signals and publishes events
On each `SIGNALS_RECEIVED` event, `AlarmProcessor` MUST check every alarm-enabled signal against its `[alarm_min, alarm_max]` range. It SHALL call `vehicle_state.set_alarm(signal, in_alarm)` for each signal. When a signal enters alarm and the cooldown window has expired (or it is the first occurrence), the processor MUST publish `AlarmFiredEvent(signal, until=now + duration_s)`.

#### Scenario: AlarmFiredEvent is published on leading edge
- **WHEN** a signal value is out of range and no cooldown is active
- **THEN** `AlarmFiredEvent` SHALL be published with `until = now + duration_s`

#### Scenario: AlarmFiredEvent is not re-published during cooldown
- **WHEN** a signal stays out of range and `now < _alarm_until[signal]`
- **THEN** no new `AlarmFiredEvent` SHALL be published

#### Scenario: Cooldown resets when alarm clears
- **WHEN** a signal returns to range before `until` expires
- **THEN** `_alarm_until[signal]` SHALL be removed so the next occurrence starts a fresh window immediately

### Requirement: Alarm audio plays while any alarm is firing
`AlarmProcessor` MUST poll `vehicle_state.is_any_alarm_firing()` every 100 ms. When at least one alarm is firing and audio is not playing, it SHALL dispatch `_play_requested` to start `alarm.wav`. When no alarm is firing and audio is playing, it SHALL dispatch `_stop_requested`. If the track ends while the alarm is still firing, playback SHALL restart from the beginning.

#### Scenario: Audio starts when alarm begins
- **WHEN** no audio was playing and a signal enters alarm
- **THEN** `alarm.wav` SHALL start playing

#### Scenario: Audio stops when all alarms clear
- **WHEN** all alarm conditions have ended
- **THEN** playback SHALL stop

#### Scenario: Audio restarts when track ends during active alarm
- **WHEN** the `alarm.wav` track ends and an alarm is still firing
- **THEN** playback SHALL restart from the beginning

### Requirement: QMediaPlayer calls are dispatched to the main thread
All `QMediaPlayer.play()` and `QMediaPlayer.stop()` calls MUST be dispatched via `Qt.ConnectionType.QueuedConnection` to respect `QMediaPlayer` thread affinity.

#### Scenario: Play is dispatched via queued connection
- **WHEN** the alarm polling thread requests audio playback
- **THEN** the actual `play()` call SHALL execute on the main Qt thread

### Requirement: Dashboard cell flashes while alarm is firing
When `DashboardScreen` receives `AlarmFiredEvent`, it MUST flash the corresponding grid cell. Flash pattern: cell background alternates black/yellow every 200 ms; text label color is set to red. Flashing continues as long as `vehicle_state.is_alarm_firing(signal)` returns true.

#### Scenario: Cell flashes on alarm
- **WHEN** `AlarmFiredEvent` is received for a signal
- **THEN** the corresponding grid cell SHALL alternate black/yellow background at 200 ms intervals with red text

#### Scenario: Cell restores on alarm end
- **WHEN** the alarm condition clears
- **THEN** the cell background SHALL restore to black and the next value update SHALL restore normal text color
