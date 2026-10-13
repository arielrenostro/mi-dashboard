## Why

On the Home screen ESC does nothing: the close callback passed to the screen is never used, so the only way to exit is the window close control. The README previously promised that ESC exits. Known issue K13. See the archived `baseline-existing-system` change (design.md, Known issues) for the full context.

## What Changes

- ESC on the Home screen closes the window and ends the app.

## Capabilities

### New Capabilities

### Modified Capabilities

- `screen-navigation`: adds the requirement "Exit with ESC on Home".

## Impact

- `app/ui/home/screen.py` (key handling). The README row "Esc" for Home is already consistent after this change.
