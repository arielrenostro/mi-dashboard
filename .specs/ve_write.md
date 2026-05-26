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
| Sound | `EVENT_SOUND` file (same `.wav` used by `EventMarker`) |

### Signal

| Signal | Type | When emitted |
|---|---|---|
| `command_requested` | `EcuCommand` | Just before dispatching to the ECU |

---

## Debounce behaviour

```
User presses ↑ or ↓
    └── ve_calibration_screen.ve_adjustment_made emitted
            └── VeWriteController.on_adjustment_made()
                    ├── timer.stop()    (cancel any pending send)
                    └── timer.start(1000)

[1 second passes with no further edits]
    └── _send_pending_changes() called
            ├── get_pending_changes() from ve_map_state
            ├── if empty → return (no-op)
            ├── log modified cells
            ├── emit command_requested(EcuCommand.WRITE_ON_MEMORY)
            └── play beep (QMediaPlayer)
```

Each edit resets the timer. Only one write is dispatched per inactivity window.

**Intent:** the 1 s delay matches typical tuning cadence — the operator makes an adjustment, watches the AFR response, then makes the next adjustment. A sub-second debounce would create redundant ECU writes without improving responsiveness.

---

## ECU command

**Command used:** `EcuCommand.WRITE_ON_MEMORY` (`#D04`)

**Current status:** the command is sent once per batch of modified cells. The actual per-cell payload format (`#D04` arguments — cell address + value encoding) is not yet specified and must be obtained from ECU firmware documentation.

**TODO:** implement per-cell addressing in `_send_pending_changes()` using `ve_map_state.get_pending_changes()` output `[(row, col, new_value)]`.

---

## Audio feedback

Uses `QMediaPlayer` + `QAudioOutput` following the same pattern as `EventMarker`:

1. Stop any currently playing sound.
2. Reset the media player position to the start.
3. Play `EVENT_SOUND`.

All `QMediaPlayer` calls happen in the main Qt thread (the controller lives in the main thread).

---

## Wiring in main.py

```python
ve_write_controller = VeWriteController(EVENT_SOUND)
ve_calibration_screen.ve_adjustment_made.connect(ve_write_controller.on_adjustment_made)
ve_write_controller.command_requested.connect(ecu_connection.send_command)
```
