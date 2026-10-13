## Why

Several components are never instantiated or connected and have no planned consumer, since the lambda loop state shown comes from ECU telemetry: the Space-hold lambda toggle, the lambda loop state filter and its registry, and a lambda flag in the shared state. Other unused code (K16) adds confusion. Keeping dead code that looks active misled the legacy documentation. See the archived `baseline-existing-system` change (design.md, Known issues) for the full context.

## What Changes

- Delete `LambdaToggle`, `KeyHoldDetector`, `LambdaLoopStateProcessor`, the processor base class, `StateProcessorRegister`.
- Remove the lambda loop flag and its accessors from the shared state.
- Remove unused code in the VE calibration screen (`populate_ve_table`) and the write controller's unused signal.
- Remove the large commented-out wiring block in `main.py`.
- No behavior change: the change declares no spec impact.

## Capabilities

### New Capabilities

### Modified Capabilities

## Impact

- Deleted: `app/event/lambda_toggle.py`, `app/event/key_hold_detector.py`, `app/state/processors/`, `app/state/register.py`.
- Edited: `app/state/state.py`, `app/ui/ve_calibration/screen.py`, `app/ui/ve_calibration/ve_write_controller.py`, `main.py`.
- Kept: `EventMarker` (wired by `wire-event-marker`) and the alarm flash handler (wired by `wire-alarm-flash`).
