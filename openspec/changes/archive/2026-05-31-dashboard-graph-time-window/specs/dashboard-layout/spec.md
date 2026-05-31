## MODIFIED Requirements

### Requirement: Graph area displays plot rows below the grid
Plot rows SHALL be rendered below the grid as defined in `config.dashboard.graph`. Each signal within a row SHALL share the same X axis (time window) but have its own Y axis scaled to `[signal.min, signal.max]`. Graph properties:
- X window: last `graph_x_seconds` seconds of data (configurable via `config.dashboard.graph_x_seconds`, default 30)
- Buffer size: `graph_x_seconds × 60` samples per signal (derived automatically — not configurable directly)
- Refresh rate: 100 ms (`QTimer`)
- Data buffer: `deque(maxlen=graph_x_seconds * 60)` per signal
- Line width: 2 px
- Left and bottom axes hidden; right axis per signal labeled with signal name
- X axis locked (no pan/zoom); Y axis interactive
- Black plot background; transparent per-signal ViewBox

#### Scenario: Graph window always shows exactly the last N seconds
- **WHEN** more than `graph_x_seconds` seconds of data have arrived for a signal
- **THEN** only data within `[t_last - graph_x_seconds, t_last]` SHALL be visible, where `t_last` is the most recent timestamp in the signal's buffer

#### Scenario: Graph window is partially empty before N seconds of data accumulate
- **WHEN** fewer than `graph_x_seconds` seconds of data have arrived since startup
- **THEN** the visible area to the left of the oldest data point SHALL be blank — no data is shown outside the buffered range

#### Scenario: graph_x_seconds is read from config
- **WHEN** `config.json` contains `dashboard.graph_x_seconds: 30`
- **THEN** all graph plots SHALL use a 30-second visible window and a deque of `30 × 60 = 1800` samples

### Requirement: Peak and minimum markers are shown on each graph curve
Each signal curve MUST have two overlaid `ScatterPlotItem` markers: a peak (max) marker and a min marker. Both SHALL be circles of size 10 in the signal color with a white border. Label text: `"{for_label(value)} {unit}"` when unit is non-empty; `"{for_label(value)}"` otherwise. Font: Arial 14 Bold in signal color. Markers SHALL be hidden when the buffer is empty. Marker X position SHALL use the timestamp of the corresponding data point.

#### Scenario: Peak marker is hidden on empty buffer
- **WHEN** a signal buffer has no data yet
- **THEN** its peak and min markers SHALL not be visible

#### Scenario: Peak marker positioned at correct timestamp
- **WHEN** the peak value is at index `i` in the buffer
- **THEN** the marker SHALL be placed at `(timestamps[i], peak_value)` on the plot
