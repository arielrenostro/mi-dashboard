# Spec: VE Map Model

Describes the in-memory representation of the 16×16 VE fuel map, the bilinear interpolation algorithm, and the editing/reset API.

Implementation: `app/ui/ve_calibration/ve_map_state.py`.

---

## Overview

The ECU uses a 16×16 lookup table (VE map) indexed by RPM (columns) and MAP pressure (rows). For any operating point that falls between breakpoints, the ECU computes the effective VE using **bilinear interpolation by distance** — potentially weighting up to four cells simultaneously.

`VeMapState` mirrors this table in memory, exposes methods to read and edit cells, and computes the same interpolation weights so the UI can accurately reflect which cells the ECU is currently using.

Module-level singleton: `ve_map_state = VeMapState()` (imported as `from app.ui.ve_calibration.ve_map_state import ve_map_state`).

---

## Axis definitions

### Default RPM axis (columns)

```
[500, 750, 1000, 1250, 1500, 1750, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]
```

16 values, ascending, in RPM.

### Default MAP axis (rows)

```
[10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160]
```

16 values, ascending, in kPa.

**Intent:** axis values match the ECU's internal breakpoints. When ECU data becomes available via the serial protocol, `load_from_ecu()` replaces both axes and the full map. Until then, the defaults are placeholders.

---

## Cell addressing

```
ve_map[row][col]
```

- `row` = MAP axis index (0 = lowest pressure, 15 = highest)
- `col` = RPM axis index (0 = lowest RPM, 15 = highest)
- Value unit: VE %, stored as `float`, range `[0.0, 1999.9]`

Initial value: `100.0` for all cells.

---

## Bilinear interpolation

Given a live RPM and MAP value, the ECU determines the effective VE by locating the four surrounding breakpoints and weighting them by inverse distance.

### Algorithm

```
1. Find col1, col2: adjacent RPM indices where rpm_axis[col1] ≤ rpm < rpm_axis[col2]
   t_rpm = (rpm - rpm_axis[col1]) / (rpm_axis[col2] - rpm_axis[col1])

2. Find row1, row2: adjacent MAP indices where map_axis[row1] ≤ map < map_axis[row2]
   t_map = (map - map_axis[row1]) / (map_axis[row2] - map_axis[row1])

3. Weights:
   w[row1][col1] = (1 - t_map) × (1 - t_rpm)
   w[row1][col2] = (1 - t_map) × t_rpm
   w[row2][col1] = t_map       × (1 - t_rpm)
   w[row2][col2] = t_map       × t_rpm

4. Effective VE = Σ (ve_map[r][c] × w[r][c]) for all (r, c)
```

Weights sum to 1.0. Cells with weight < 0.001 are omitted from the result.

### Edge clamping

| Condition | Behaviour |
|---|---|
| `rpm ≤ rpm_axis[0]` | `col1 = col2 = 0`, `t_rpm = 0` |
| `rpm ≥ rpm_axis[-1]` | `col1 = col2 = 15`, `t_rpm = 0` |
| `map ≤ map_axis[0]` | `row1 = row2 = 0`, `t_map = 0` |
| `map ≥ map_axis[-1]` | `row1 = row2 = 15`, `t_map = 0` |

When `col1 == col2` or `row1 == row2`, duplicate dict keys are collapsed by summing their weights, yielding 1 or 2 active cells instead of 4.

**Implementation:** uses `bisect.bisect_right` on both axes. No external dependencies.

---

## API

| Method | Signature | Description |
|---|---|---|
| `load_from_ecu` | `(rpm_axis, map_axis, ve_map)` | Replace axes and map; reset `modified_cells` |
| `get_cell` | `(row, col) → float` | Read a single cell value |
| `set_cell` | `(row, col, value)` | Write a cell; clamp to `[0, 1999.9]`; update `modified_cells` |
| `reset` | `()` | Restore all cells from `original_ve_map`; clear `modified_cells` |
| `adjust_ve` | `(rpm, map_val, delta)` | Apply `delta` distributed by interpolation weights |
| `calculate_interpolation_weights` | `(rpm, map_val) → dict` | Returns `{(row, col): float}` |
| `get_pending_changes` | `() → list[(row, col, value)]` | All cells that differ from original |

### `set_cell` modification tracking

A cell is added to `modified_cells` when `|new_value - original_value| > 0.05`. It is removed from `modified_cells` when the value returns within that tolerance.

### `adjust_ve` distribution

For each active cell `(row, col)` with weight `w`:
```
new_value = current_value + delta × w
```

Total effective VE change equals `delta`, distributed proportionally across the active cells.

---

## ECU data source (TODO)

The default axis values and map contents are placeholders. The actual ECU map must be read at startup using the serial protocol.

- **Suspected frame type:** `EcuResponse.MESS_DATA_3` (`#D03`) — not yet confirmed.
- **Required action:** extend `EcuConnection` to request and parse `#D03` frames, then call `ve_map_state.load_from_ecu(...)`.
- Until this is implemented, the UI shows the default 100.0 placeholders.
