## Why

With the new per-frame event model, `SignalProcessor` publishes `SignalsReceivedEvent` independently for each frame (D01, D02, D03). Dashboard graph buffers accumulate one sample per event using a sequential index as X axis, so signals from different frames get their data points at different indices — making multi-signal graphs visually desynchronized.

## What Changes

- `SignalsReceivedEvent` gains a `timestamp: float` field (populated automatically via `time.monotonic` at publish time — no changes to `SignalProcessor` logic)
- `DashboardScreen` stores a parallel timestamp deque alongside each signal's value deque
- Graph curves render using real timestamps as the X axis (`setData(xs, ys)`) instead of implicit sequential indices
- X range is updated dynamically in `update_graph` from the actual data timestamps
- Peak/min marker positions use the timestamp of the corresponding data point as their X coordinate

## Capabilities

### New Capabilities
- `graph-time-axis`: Dashboard graphs use `time.monotonic` timestamps as the X axis, naturally aligning signals from different frames without batching or delaying events

### Modified Capabilities
- `data-pipeline`: `SignalsReceivedEvent` gains a `timestamp` field — no behavioral change to publish timing or frequency

## Impact

- `app/event/app_events.py`: Add `timestamp: float` field to `SignalsReceivedEvent`
- `app/ui/dashboard/screen.py`: Timestamp deques, dynamic X range, `setData(xs, ys)`, marker positions
- No changes to `SignalProcessor`, `AlarmProcessor`, `VehicleState`, or `LogWriter`
