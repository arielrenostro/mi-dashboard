# Spec: Alarm System

Describes how limit alarms are detected, tracked, played, and displayed.

Implementation: `app/alarm/processor.py`, `app/state/state.py`, `app/ui/dashboard/screen.py`.

---

## Alarm configuration per signal

Each signal in `signal.py` carries an `alarm` block:

| Field | Type | Description |
|---|---|---|
| `enabled` | bool | Whether the alarm can fire for this signal |
| `min` | float \| None | Lower bound. `None` = no lower bound |
| `max` | float \| None | Upper bound. `None` = no upper bound |
| `duration_s` | float | How long one alarm event lasts (default 2.0 s) |

An alarm condition exists when `enabled = true` AND (`value < min` OR `value > max`).

---

## Alarm lifecycle

```
event_bus → SIGNALS_RECEIVED
    │
    ▼
AlarmProcessor.process_signals(parsed_data)
    │
    ├─ for each signal:
    │     compute in_alarm (value vs. min/max via _check_in_alarm)
    │     call vehicle_state.set_alarm(signal, in_alarm)
    │
    │     if in_alarm:
    │         if now >= _alarm_until[signal]:      ← cooldown expired (or first occurrence)
    │             new_until = now + duration_s
    │             _alarm_until[signal] = new_until
    │             event_bus.publish(AlarmFiredEvent(signal, until=new_until))
    │     else:
    │         _alarm_until.pop(signal)             ← reset cooldown when alarm clears
    │
    ▼
event_bus → ALARM_FIRED
    └──► DashboardScreen.fire_field_alarm(signal)   (only when dashboard is active)

AlarmProcessor.run() polls vehicle_state.is_any_alarm_firing() every 100 ms
    ├─ any alarm firing AND not playing → _play_requested.emit()
    └─ no alarm firing AND playing     → _stop_requested.emit()
```

**Cooldown rule:** `AlarmFiredEvent` is published at most once per `duration_s` window. If the signal stays in alarm past the `until` timestamp, a new event is published for the next window. If the alarm clears before `until` expires, the cooldown is reset — the next alarm occurrence starts a fresh window immediately.

**`until` field:** subscribers receive the expiry timestamp and can use it to decide how long to show or sound the alarm (e.g. DashboardScreen flashes for as long as `vehicle_state.is_alarm_firing()` returns true).

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

When `AlarmFiredEvent` fires for a signal, `DashboardScreen.fire_field_alarm(signal)` is called (subscribed in `on_activated()`; unsubscribed when the screen is hidden).

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
- Normal label color is restored by `DashboardScreen.update_display()` on the next frame where the value is within range.

---

## Lambda loop alarm — special case

The lambda loop state reported by the ECU can transiently read "open" during deceleration fuel cut, even when the loop is actually closed. This is **not** an alarm condition — it is handled by `LambdaLoopStateProcessor` filtering these transient states from `VehicleState`.

See `data_pipeline.md` → Lambda Loop State section.
