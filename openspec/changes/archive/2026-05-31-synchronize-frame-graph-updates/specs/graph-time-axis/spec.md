## ADDED Requirements

### Requirement: SignalsReceivedEvent carries a monotonic timestamp
`SignalsReceivedEvent` SHALL include a `timestamp: float` field populated with `time.monotonic()` at the moment of publication. All existing consumers that do not read this field are unaffected.

#### Scenario: Timestamp is set automatically at publish time
- **WHEN** `SignalProcessor` publishes `SignalsReceivedEvent`
- **THEN** `event.timestamp` SHALL be a positive float from `time.monotonic()`, set via `default_factory` — no call-site change required in `SignalProcessor`

### Requirement: DashboardScreen graphs use timestamps as the X axis
`DashboardScreen` SHALL maintain a parallel `timestamps` deque for each signal in the graph. Graph curves SHALL be rendered with `curve.setData(xs, ys)` where `xs` is the list of timestamps and `ys` is the list of values.

#### Scenario: Signals from D01 and D02 are aligned on the time axis
- **WHEN** a D01 signal (e.g. RPM at t=100 ms) and a D02 signal (e.g. LAMBDA at t=102 ms) are rendered on the same graph
- **THEN** both curves SHALL use their respective timestamps as X coordinates, placing them correctly on the shared time axis with a natural offset that is visually imperceptible at graph scale

#### Scenario: Timestamp deque grows in lockstep with value deque
- **WHEN** `on_signal_received` appends a value to `buffers[signal]`
- **THEN** it SHALL also append `event.timestamp` to `timestamps[signal]`, keeping both deques at equal length at all times

#### Scenario: Buffer size is still governed by graph_x_size
- **WHEN** the number of samples in a signal's buffer reaches `graph_x_size`
- **THEN** both `buffers[signal]` and `timestamps[signal]` SHALL drop the oldest entry (deque maxlen applies to both)

### Requirement: X range is set dynamically from buffer timestamps
`DashboardScreen` SHALL update the X range of each plot's `base_view` in `update_graph` using the first and last timestamps from the signal buffer, replacing the static `setXRange(0, graph_x_size + 1)` set at construction time. `base_view` SHALL be stored per signal in `self.base_views` during `_create_graphs`.

#### Scenario: X range covers the visible buffer window
- **WHEN** `update_graph` fires and a signal buffer is non-empty
- **THEN** `base_view.setXRange(ts[0], ts[-1], padding=0.01)` SHALL be called for the corresponding plot, so all curves in that plot are visible within the current time window

#### Scenario: X range is not set when buffer is empty
- **WHEN** `update_graph` fires and a signal buffer is empty (e.g. at startup)
- **THEN** no `setXRange` call SHALL be made for that plot to avoid a zero-width range error

### Requirement: Peak and min marker positions use timestamps as the X coordinate
Peak and minimum markers and their labels SHALL use the timestamp of the corresponding data point as their X coordinate, not the array index.

#### Scenario: Peak marker is placed at the correct time position
- **WHEN** `update_graph` identifies the maximum value at array index `i`
- **THEN** the peak marker SHALL be placed at `(ts[i], value)` and the label SHALL be positioned at `ts[i]` on the X axis
