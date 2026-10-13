## Why

The event marker (Enter stamps `MARK` on the next CSV row and beeps) exists in code but is not connected, so the Event column is always empty. The user wants it working so interesting moments can be flagged during a run. See the archived `baseline-existing-system` change (design.md, Known issues) for the full context.

## What Changes

- Enter / Return on the Dashboard and the VE calibration screen plays a configurable sound and marks the next logged row with `MARK`.
- New setting `datalog.mark_sound` (default `alarm.wav`).
- Home keeps Enter for opening a screen and does not mark.

## Capabilities

### New Capabilities

### Modified Capabilities

- `datalog`: "Event column" no longer says nothing requests a mark; adds "Manual event mark".
- `app-configuration`: new `datalog.mark_sound` setting.

## Impact

- `app/ui/window.py` (key event signal, scoped to data screens), `main.py` (create marker, connect to log writer), `app/config.py`, `README.md`.
