## Context

The ECU streams D01, D02, and D03 frames sequentially within each cycle. After the per-frame event refactor, `SignalProcessor` publishes `SignalsReceivedEvent` once per frame. `DashboardScreen.on_signal_received` appends to signal deques immediately on each event, using the deque index as an implicit X axis for graphs.

The desync happens when the 100 ms render timer fires between two frames of the same cycle (e.g., between D01 and D02): one signal has N+1 samples, another has N — they render at different X positions on a shared axis.

## Goals / Non-Goals

**Goals:**
- Signals from different frames are always visually aligned on the same graph
- Zero delay in `SIGNALS_RECEIVED` events — alarms and card updates remain immediate
- Zero sample loss — every frame's data reaches the graph buffer
- Change is self-contained: only `app_events.py` and `screen.py` change

**Non-Goals:**
- Changing `SignalProcessor` publish behavior
- Adding new event types
- Displaying real wall-clock time on the X axis (axis is hidden)

## Decisions

### Timestamps as X axis instead of sequential indices

**Decision**: Add `timestamp: float = field(default_factory=time.monotonic)` to `SignalsReceivedEvent`. `DashboardScreen` stores a parallel `timestamps` deque per signal and uses `curve.setData(xs, ys)` with real timestamps.

**Rationale**: The 2 ms inter-frame gap between D01 and D02 at 115200 baud is ~0.01% of a 15-second graph window — visually indistinguishable from zero. Time is the natural common axis that makes signals self-aligning regardless of when the render timer fires. No batching, no event delay, no sample loss.

Alternatives considered:
- **D01-boundary flush in SignalProcessor**: delays `SIGNALS_RECEIVED` by one cycle (~50–100 ms), which delays alarms. Rejected.
- **Snapshot + render timer**: timer-based append limits graph resolution to timer frequency (10 Hz), losing ECU samples if ECU > 10 Hz. Rejected.
- **`CYCLE_COMPLETED` second event**: keeps `SIGNALS_RECEIVED` immediate but adds a new event type and still delays graph data by one cycle. More complexity for no gain over timestamp approach. Rejected.

### `time.monotonic` over `time.time`

**Decision**: Use `time.monotonic()` as the timestamp source.

**Rationale**: Monotonic clock never jumps backward (no NTP adjustments), giving stable inter-point distances on the graph. Wall-clock accuracy is irrelevant since the X axis is hidden.

### Dynamic X range set from buffer contents

**Decision**: Remove the static `setXRange(0, graph_x_size + 1)` set during construction. In `update_graph`, call `base_view.setXRange(ts[0], ts[-1], padding=0.01)` from the first signal's timestamp buffer in each plot.

**Rationale**: With timestamps as X values, the range must reflect actual data extent. The `base_view` controls all linked signal ViewBoxes via `setXLink`, so one call per plot widget is sufficient. A small padding (1%) keeps the last data point from being clipped at the edge.

`base_view` (currently a local variable in `_create_graphs`) must be stored per signal in `self.base_views: Dict[Signal, ViewBox]` so `update_graph` can reach it.

### `graph_x_size` remains sample count, not seconds

**Decision**: `graph_x_size` stays as the `deque(maxlen=...)` limit — the number of samples kept in memory.

**Rationale**: The visible time window is now determined by the actual ECU rate × `graph_x_size`. At 20 Hz, `graph_x_size=150` shows 7.5 seconds; at 10 Hz, 15 seconds. This adapts naturally to the ECU rate without configuration.

## Risks / Trade-offs

- **Peak/min marker X must become a timestamp**: `value_index = data.index(value)` is still valid to locate the sample, but `markers[signal].setData([value_index], [value])` must become `markers[signal].setData([ts[value_index]], [value])`. The same applies to `labels[signal].setPos(...)`. Straightforward change but easy to miss.
- **`base_view` not currently stored**: It is a local variable in `_create_graphs`. Forgetting to store it would mean `update_graph` cannot set the X range, leaving the graph at the initial static range. Mitigated by the tasks checklist.
- **First render with partial buffer**: On startup, `ts[0]` and `ts[-1]` may be very close (one sample). `padding=0.01` prevents a zero-width range from crashing pyqtgraph.
