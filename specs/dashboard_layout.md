# Spec: Dashboard Layout

Describes the visual layout of the dashboard: the numeric grid and the signal graphs.

Implementation: `app/dashboard/grid.py` (layout data), `app/dashboard/dashboard.py` (rendering).

---

## General

- The dashboard runs **full-screen** with a black background.
- Layout is a vertical stack: numeric grid on top, graphs below.
- The window title is `"Master Injection Dashboard"`.

---

## Numeric grid

A 2-row × N-column grid of signal cells. Each cell shows the signal's name, unit, and current value.

### Layout

```
Row 0: RPM | VSS | MAP | BOOST | CLT | IAT | POWER
Row 1: LAMBDA | LAMBDA_TARGET | FUEL_TRIM | BOOST_TARGET | INJ_UTIL | IGN | TORQUE
```

### Cell anatomy

Each cell is a black `QWidget` with a vertical layout and 8 px horizontal / 4 px vertical margins:

```
┌─────────────────────────────┐
│ Signal Name (Unit)    gray  │  ← small label, Arial 14 Bold, left-aligned
│                      VALUE  │  ← big label, Arial 56 Bold, right-aligned
└─────────────────────────────┘
```

- **Small label**: `"{name} ({unit})"` if unit is non-empty; `"{name}"` otherwise. Color: gray.
- **Big label**: initial value `"--"`. Color: signal's `color` field from `signals.md` when normal; `red` when value is outside alarm range.

### Value update

- Values are updated every time a new `parsed_data` dict is emitted by `SignalProcessor`.
- If the signal's value is outside `[alarm_min, alarm_max]`, the big label color changes to red.
- If an alarm is also firing (tracked in `VehicleState`), the cell background flashes — see `alarm_system.md`.

---

## Graphs

Three plot rows, rendered below the grid. Each row is a `pyqtgraph PlotWidget` with one shared X axis and one independent Y axis per signal (right-side axes).

### Layout

```
Graph row 0: LAMBDA | LAMBDA_TARGET | FUEL_TRIM
Graph row 1: BOOST  | BOOST_TARGET  | MAP
Graph row 2: POWER  | TORQUE
```

Each signal within a row shares the same X axis (time window) but has its own Y axis scaled to `[signal.min, signal.max]`.

### Graph behavior

| Property | Value |
|---|---|
| X window size | 150 data points (configurable via `graph_x_size` in `main.py`) |
| Refresh rate | 100 ms (`QTimer`) |
| Data buffer | `deque(maxlen=graph_x_size)` per signal |
| Line width | 2 px |
| Axes | Left and bottom axes hidden; right axis per signal, labeled with signal name |
| Mouse interaction | X axis locked (no pan/zoom); Y axis interactive |
| Background | Transparent per-signal ViewBox over a shared black plot background |

### Peak and minimum markers

Each signal in each graph has two markers overlaid on the curve:

| Marker | Shape | Color | Label anchor |
|---|---|---|---|
| Peak (max) | Circle, size 10 | Signal color, white border | (0.5, 1.5) |
| Min | Circle, size 10 | Signal color, white border | (0.5, 1.5) |

Label text: `"{for_label(value)} {unit}"` if unit is non-empty; `"{for_label(value)}"` otherwise. Font: Arial 14 Bold, signal color. Markers are hidden when the buffer is empty.
