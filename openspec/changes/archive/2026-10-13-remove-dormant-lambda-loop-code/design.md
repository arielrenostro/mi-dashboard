## Context

`LambdaToggle` and `KeyHoldDetector` were meant for a Space-hold toggle that is no longer wanted. `LambdaLoopStateProcessor` and its registry maintain a flag in `VehicleState` that nothing reads; the registry also connects a text signal to a slot with a different signature and would fail if wired.

## Goals / Non-Goals

**Goals:** remove code with no consumer, leave behavior unchanged.

**Non-Goals:** touching `EventMarker`, the alarm flash handler, or the O / P keys.

## Decisions

- **Order:** apply after `wire-event-marker` and `wire-alarm-flash`, because all three edit `main.py`; the commented block removal then also drops any stale TODOs. If applied earlier, keep the TODO lines for those two features.
- **`KeyHoldDetector`:** removed because its only intended user is the Space toggle; reintroduce from git history if a hold action is needed.
- **No spec change:** the removed pieces appear in no capability spec.

## Risks / Trade-offs

- [A removed class is still imported somewhere] -> search for references before deleting and run the app with the mock afterwards.
