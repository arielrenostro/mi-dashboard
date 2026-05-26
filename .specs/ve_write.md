# Spec: VE Map Write Controller

Describes the deferred ECU write behaviour: debounce timing, command dispatch, and audio feedback.

Implementation: `app/ui/ve_calibration/ve_write_controller.py`, instantiated inside `VeCalibrationScreen`.

---

## Overview

When the operator edits the VE map (↑ or ↓ keys), changes accumulate in `VeMapState`. To avoid flooding the ECU with a write command on every key press, a 1-second debounce timer is used: the command is sent only after 1 second of inactivity. A beep confirms the dispatch.

---

## VeWriteController

**Class:** `VeWriteController` (`app/ve_calibration/ve_write_controller.py`)

| Property | Value |
|---|---|
| Base class | `QObject` |
| Debounce duration | 1000 ms |
| Timer type | Single-shot (`QTimer`, `setSingleShot(True)`) |
| Sound | `ve_sound` `.wav` configured in `config.ve_calibration` |

`VeWriteController` has no outbound signals. It dispatches ECU commands directly via `get_ecu_connection().send_command(cmd, values)`.

---

## Debounce behaviour

```
User presses ↑ or ↓ (or R for reset)
    └── VeCalibrationScreen calls self._writer.on_adjustment_made() directly
            ├── timer.stop()    (cancel any pending send)
            └── timer.start(1000)

[1 second passes with no further edits]
    └── _send_pending_rows() called
            ├── ve_map_state.get_pending_rows()
            ├── if empty → return (no-op)
            ├── for each pending row:
            │       values = ve_map_state.get_row_raw_values(row)
            │       cmd = EcuCommand[f"VE_ROW_{row + 1}"]
            │       ve_map_state.mark_row_sent(row)
            │       get_ecu_connection().send_command(cmd, values)
            └── play beep (QMediaPlayer)
```

Each edit resets the timer. Only one write batch is dispatched per inactivity window.

**Intent:** the 1 s delay matches typical tuning cadence — the operator makes an adjustment, watches the AFR response, then makes the next adjustment. A sub-second debounce would create redundant ECU writes without improving responsiveness.

---

## ECU commands

One `VE_ROW_N` command is sent per modified row (N = 1–16), carrying the full 16-cell row as raw values. Modified rows are marked as sent before the command is dispatched to avoid re-sending if the timer fires again before the ECU confirms.

---

## Audio feedback

Uses `QMediaPlayer` + `QAudioOutput`:
1. Stop any currently playing sound.
2. Play `ve_sound`.

All `QMediaPlayer` calls happen in the main Qt thread (the controller lives in the main thread).

---

## Wiring

`VeWriteController` is owned by `VeCalibrationScreen`. No external wiring is required.

`VeCalibrationScreen` calls `self._writer.on_adjustment_made()` directly after every VE adjustment — no signal, no external consumer.
