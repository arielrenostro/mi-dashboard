## Context

`AlarmProcessor` already emits a signal on alarm onset. `DashboardScreen.fire_field_alarm` implements the flash with chained single-shot timers that stop when the alarm is no longer firing. `update_display` skips recoloring when the alarm is enabled, expecting the flash to color the card.

## Goals / Non-Goals

**Goals:** connect the pieces and make colors consistent for enabled and disabled alarms.

**Non-Goals:** changing alarm limits, audio behavior or the 2 second firing window; flashing on other screens.

## Decisions

- **Forwarding path:** the Dashboard lives inside the window, so the window exposes a slot that forwards the notification to it, and `main.py` connects the alarm processor to that slot. Alternative: expose the dashboard instance; rejected to keep screens encapsulated.
- **Color rule:** red whenever outside limits (the behavior confirmed for disabled-alarm signals), extended to enabled ones; the "skip when firing" guard stays so the flash alternates text/background without being overwritten each frame.
- **Re-trigger:** the onset notification is emitted only when the signal is not firing, so one flash chain exists per episode; a chain ends when firing stops.

## Risks / Trade-offs

- [Flash chain could duplicate if onset fires twice within an episode] -> the onset rule prevents it; verify with a signal oscillating around its limit.
- [Flash runs while the Dashboard is hidden] -> timers are cheap and the card is not visible; acceptable.
