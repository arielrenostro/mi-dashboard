# Spec: Alarm System

Describes how limit alarms are detected, tracked, played, and displayed.

Implementation: `app/alarm/processor.py`, `app/vehicle/state.py`, `app/dashboard/dashboard.py`.

---

## Alarm configuration per signal

Each signal in `signals.md` carries an `alarm` block:

| Field | Type | Description |
|---|---|---|
| `enabled` | bool | Whether the alarm can fire for this signal |
| `min` | float \| None | Lower bound (inclusive). `None` = no lower bound |
| `max` | float \| None | Upper bound (inclusive). `None` = no upper bound |

An alarm condition exists when `enabled = true` AND (`value < min` OR `value > max`).

---

## Alarm lifecycle

```
SignalProcessor emits parsed_data
    │
    ▼
AlarmProcessor.process_signals(parsed_data)
    │
    ├─ for each signal:
    │     compute in_alarm (value vs. min/max)
    │     call vehicle_state.set_alarm(signal, in_alarm)
    │     if in_alarm AND alarm was NOT already firing:
    │         emit AlarmProcessor.emitter(signal)   ← leading edge only
    │
    ▼
vehicle_state stores alarm timestamp (time.time())

    ─ alarm is considered "firing" for 2 seconds from the last set_alarm(True) call ─

AlarmProcessor.run() polls vehicle_state.is_any_alarm_firing() every 100 ms
    │
    ├─ any alarm firing AND not playing → _play_requested.emit()
    └─ no alarm firing AND playing     → _stop_requested.emit()
```

**Alarm duration:** 2 seconds (constant `ALARM_DURATION` in `app/vehicle/state.py`). Each new out-of-range frame resets the 2-second window, so the alarm stays active as long as the condition persists.

---

## Audio behavior

| State | Action |
|---|---|
| Alarm starts (was not firing) | Start playing `alarm.wav` |
| Alarm ends (was firing) | Stop playback |
| Track ends while alarm still firing | Restart playback from beginning |

- Audio is played by a `QMediaPlayer` owned by `AlarmProcessor`.
- `play()` and `stop()` are dispatched to the main thread via `Qt.ConnectionType.QueuedConnection` to respect `QMediaPlayer` thread affinity.

---

## Visual behavior

When `AlarmProcessor.emitter` fires for a signal, `Dashboard.fire_field_alarm(signal)` is called on the leading edge of each alarm.

### Flash pattern

```
t=0 ms   → schedule first flash (QTimer.singleShot 0)
t=0 ms   → label color = red
            if i is even:  cell background = black
            if i is odd:   cell background = yellow
t=200 ms → if alarm still firing: schedule next flash (i+1), else restore
```

- The flash repeats every 200 ms alternating black/yellow background.
- When the alarm stops firing, the cell background is restored to black.
- Normal label color (signal's `color`) is restored by `Dashboard.update_display()` on the next frame where the value is within range.

---

## Lambda loop alarm — special case

The lambda loop state reported by the ECU can transiently read "open" during deceleration fuel cut, even when the loop is actually closed. This is **not** an alarm condition — it is handled by `LambdaLoopStateProcessor` filtering these transient states from `VehicleState`.

See `data_pipeline.md` → Lambda Loop State section.
