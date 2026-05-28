## ADDED Requirements

### Requirement: Dashboard runs full-screen with black background
The dashboard MUST display full-screen with a black background, window title `"Master Injection Dashboard"`. Layout SHALL be a vertical stack: numeric grid on top, graphs below.

#### Scenario: Dashboard fills the screen
- **WHEN** the Dashboard screen is activated
- **THEN** the window SHALL be full-screen with a black background

### Requirement: Numeric grid shows a 2×N cell layout
The grid SHALL be 2 rows × N columns. Row 0: `RPM | VSS | MAP | BOOST | CLT | IAT | POWER`. Row 1: `LAMBDA | LAMBDA_TARGET | FUEL_TRIM | BOOST_TARGET | INJ_UTIL | IGN | TORQUE`.

Each cell MUST contain:
- Small label (top-left, Arial 14 Bold, gray): `"{name} ({unit})"` when unit is non-empty; `"{name}"` otherwise
- Big label (right-aligned, Arial 56 Bold): initial `"--"`, value color from signal's `color` field when normal, `red` when outside alarm range

Cell MUST have 8 px horizontal and 4 px vertical margins.

#### Scenario: Cell shows signal name with unit
- **WHEN** a signal with unit `"RPM"` is displayed
- **THEN** the small label SHALL read `"RPM (RPM)"`

#### Scenario: Value turns red when outside alarm range
- **WHEN** the signal value is outside `[alarm_min, alarm_max]`
- **THEN** the big label color SHALL be `red`

### Requirement: Values are updated on every SIGNALS_RECEIVED event
The dashboard MUST update all cell values each time a new `parsed_data` dict is received from `SignalProcessor`.

#### Scenario: Display updates on each frame
- **WHEN** a new frame is parsed by `SignalProcessor`
- **THEN** all grid cell values SHALL be refreshed

### Requirement: Graph area displays three plot rows below the grid
Three `pyqtgraph PlotWidget` rows SHALL be rendered below the grid:
- Row 0: `LAMBDA | LAMBDA_TARGET | FUEL_TRIM`
- Row 1: `BOOST | BOOST_TARGET | MAP`
- Row 2: `POWER | TORQUE`

Each signal within a row SHALL share the same X axis (time window) but have its own Y axis scaled to `[signal.min, signal.max]`. Graph properties:
- X window: 150 data points (configurable via `graph_x_size`)
- Refresh rate: 100 ms (`QTimer`)
- Data buffer: `deque(maxlen=graph_x_size)` per signal
- Line width: 2 px
- Left and bottom axes hidden; right axis per signal labeled with signal name
- X axis locked (no pan/zoom); Y axis interactive
- Black plot background; transparent per-signal ViewBox

#### Scenario: Graph window scrolls over time
- **WHEN** more than 150 samples have arrived for a signal
- **THEN** only the last 150 samples SHALL be visible in the graph

### Requirement: Peak and minimum markers are shown on each graph curve
Each signal curve MUST have two overlaid `ScatterPlotItem` markers: a peak (max) marker and a min marker. Both SHALL be circles of size 10 in the signal color with a white border. Label text: `"{for_label(value)} {unit}"` when unit is non-empty; `"{for_label(value)}"` otherwise. Font: Arial 14 Bold in signal color. Markers SHALL be hidden when the buffer is empty.

#### Scenario: Peak marker is hidden on empty buffer
- **WHEN** a signal buffer has no data yet
- **THEN** its peak and min markers SHALL not be visible
