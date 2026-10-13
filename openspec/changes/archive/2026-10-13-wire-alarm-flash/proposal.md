## Why

The alarm flash (grid card alternating black/yellow while an alarm fires) exists but is not connected. Worse, signals with the alarm enabled never turn red on the grid, because the grid defers coloring to the flash; only disabled-alarm signals with limits turn red. Known issue K2. See the archived `baseline-existing-system` change (design.md, Known issues) for the full context.

## What Changes

- The alarm onset notification is connected to the Dashboard so the card flashes while the alarm is firing.
- The grid shows red for any signal outside its limits, regardless of whether the alarm is enabled; while a flash runs, the flash controls the card colors.

## Capabilities

### New Capabilities

### Modified Capabilities

- `alarms`: adds "Visual alarm flash".
- `dashboard`: "Out-of-limit color for non-alarm signals" is renamed to "Out-of-limit color" and covers alarm-enabled signals too.

## Impact

- `main.py` and `app/ui/window.py` (forward the notification to the Dashboard), `app/ui/dashboard/screen.py` (`update_display`), `README.md` (remove the "pending wiring" remark).
