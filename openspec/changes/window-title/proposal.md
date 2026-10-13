## Why

The old documentation stated the window title as "Master Injection Dashboard", but the code never sets one. Known issue K14. See the archived `baseline-existing-system` change (design.md, Known issues) for the full context.

## What Changes

- The application window has the title `Master Injection Dashboard`.

## Capabilities

### New Capabilities

### Modified Capabilities

- `screen-navigation`: adds the requirement "Window title".

## Impact

- `app/ui/window.py`.
