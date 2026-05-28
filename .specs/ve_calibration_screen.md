# Spec: VE Calibration Screen

Describes the real-time VE map calibration screen: layout, live data display, interpolation highlighting, and keyboard editing.

Implementation: `app/ui/ve_calibration/screen.py`.
Data model: see `ve_map_model.md`.
Write protocol: see `ve_write.md`.

---

## Overview

The VE Calibration screen lets the operator view the ECU's 16×16 VE fuel map in real time and edit cell values while the engine is running. Edits are distributed across the active interpolation cells proportional to their weights, mirroring the ECU's own interpolation behaviour.

---

## Layout

Three vertical zones, no padding between them, separated by 1 px `#333333` lines:

```
┌────────────────────────────────────────────────────────────┐
│ TOP BAR (80 px fixed)                                      │
│  RPM │ MAP │ VE │ Lambda │ Lambda Target │ Fuel Trim │ Loop│
├────────────────────────────────────────────────────────────┤
│ CENTRE (stretch, fills remaining height)                   │
│                                                            │
│  ┌─────────────────────────┬──────────────────────────┐   │
│  │ Mapa VE (16×16)   60%   │    Gráfico VE      40%   │   │
│  │ QTableWidget 16×17      │    pyqtgraph heatmap     │   │
│  └─────────────────────────┴──────────────────────────┘   │
├────────────────────────────────────────────────────────────┤
│ FOOTER (40 px fixed)                                       │
│  ↑ +6 VE  ↓ -6 VE  Espaço Loop Open/Closed  R Resetar ESC│
└────────────────────────────────────────────────────────────┘
```

---

## Zone 1: Top bar

Seven equally-spaced signal cells in a horizontal row. Each cell follows the same anatomy as the Dashboard grid cell but at smaller font sizes:

| Element | Font | Color |
|---|---|---|
| Signal name + unit | Arial 12 Bold | Gray (`#888888`) |
| Current value | Arial 40 Bold | White (`#FFFFFF`) |

### Signals displayed (in order)

| Signal | Unit | Special coloring |
|---|---|---|
| `RPM` | RPM | — |
| `MAP` | kPa | — |
| `VE` | % | — |
| `LAMBDA` | λ | — |
| `LAMBDA_TARGET` | λ | — |
| `FUEL_TRIM` | % | — |
| `LAMBDA_LOOP` | — | Green (`#00FF00`) = Closed; Orange (`#FF8800`) = Open |

Values are updated every time `process_signals(parsed_data)` is called (driven by `SignalProcessor.emitter`).

---

## Zone 2a: VE Map Table

`QTableWidget(16, 17)`:
- **Column 0:** MAP axis label (dark header column, `#111111` background, gray text)
- **Columns 1–16:** VE values for each RPM breakpoint

Horizontal header (column labels): `"MAP\RPM"` for col 0, then RPM axis values (`"500"`, `"750"`, …) for cols 1–16.
Vertical header (row labels): MAP axis values (`"10"`, `"20"`, …).

| Property | Value |
|---|---|
| Cell font | Arial 10 |
| Default cell background | `#1A1A1A` |
| Default cell text | White (`#FFFFFF`) |
| Header background | `#111111` |
| Header text | Gray (`#888888`) |
| Gridlines | `#333333` |
| Selection mode | None (read-only interaction) |
| Editing | Disabled |

### Highlight: active interpolation cells

Every 100 ms, the screen reads the current RPM and MAP from `vehicle_state`, calls `ve_map_state.calculate_interpolation_weights()`, and applies a background color blend to active cells:

```
cell_color = lerp(#1A1A1A, #FF6600, weight)
```

Where `weight ∈ (0, 1]` is the interpolation weight for that cell. Cells not in the weights dict revert to `#1A1A1A`.

### Highlight: modified cells

Cells present in `ve_map_state.modified_cells` have their text color changed to `#00CCFF`. All other cells use white (`#FFFFFF`).

Both highlights are applied together in the same 100 ms update cycle.

---

## Zone 2b: VE Map Graph

`pyqtgraph PlotWidget` heatmap displayed at 40% of the centre area width.

| Property | Value |
|---|---|
| X axis | RPM (range: `rpm_axis[0]` to `rpm_axis[-1]`) |
| Y axis | MAP in kPa (range: `map_axis[0]` to `map_axis[-1]`) |
| Color encoding | VE value via color map (CET-L1 preferred; fallback: `inferno`) |
| Data orientation | `ImageItem` with shape `(16, 16)`, axes aligned to RPM (x) × MAP (y) |

### Active interpolation indicator

A `ScatterPlotItem` overlaid on the heatmap shows the **weighted centroid** of the active interpolation cells:

```
centroid_rpm = Σ (rpm_axis[col] × weight)  for (row, col) in active cells
centroid_map = Σ (map_axis[row] × weight)  for (row, col) in active cells
```

Scatter style: red fill, white border, size 12. Hidden when no active cells.

The heatmap and scatter are updated in the same 100 ms cycle as the table highlight.

---

## Zone 3: Footer

Single-line label with all keyboard shortcuts, centered, gray (`#888888`), Arial 12, 40 px fixed height:

```
↑ +5 VE   ↓ -5 VE   G %VE   O Open Loop   P Close Loop   R Resetar   ESC Voltar
```

---

## Update cycle

A `QTimer` fires every 100 ms while the screen is active:

1. Read RPM and MAP from `vehicle_state`.
2. Calculate interpolation weights via `ve_map_state.calculate_interpolation_weights()`.
3. Apply table interpolation highlight (`highlight_interpolation(weights)`).
4. Apply modified-cell highlight (`mark_modified_cells(ve_map_state.modified_cells)`).
5. Refresh all VE cell text values from `ve_map_state.ve_map`.
6. Update heatmap image and scatter point (`update_heatmap(...)`).

Timer is started in `on_activated()` and stopped in `on_deactivated()` to avoid updates while the screen is hidden.

---

## Keyboard editing

See `keyboard_actions.md` for the full action table. Summary of actions scoped to this screen:

| Key | Effect |
|---|---|
| `↑` | `ve_map_state.adjust_ve(rpm, map, +5.0)` |
| `↓` | `ve_map_state.adjust_ve(rpm, map, -5.0)` |
| `G` | Opens `PercentageDialog`; on confirm calls `ve_map_state.adjust_ve_by_percentage(rpm, map, pct)` |
| `O` | Sends `LAMBDA_LOOP_OPEN` to ECU |
| `P` | Sends `LAMBDA_LOOP_CLOSE` to ECU |
| `R` | `ve_map_state.reset()` |
| `Space` (2 s hold) | Toggle lambda loop (global action, handled by `KeyHoldDetector` + `LambdaToggle`) |
| `ESC` | Return to home (handled by `AppWindow`) |

After each edit, `self._writer.on_adjustment_made()` is called directly to trigger the write debounce timer (see `ve_write.md`).

---

## Percentage Dialog (`PercentageDialog`)

Implementation: `app/ui/ve_calibration/percentage_dialog.py`.

A `QDialog` modal that captures a percentage value from the user for proportional VE increment.

### Behavior

1. Opened when `G` is pressed while RPM and MAP data are available.
2. Displays a single `QLineEdit` with `QDoubleValidator` (range −100 to 100, 2 decimal places).
3. Press **Enter** or click **Confirmar** → `accept()`. The dialog exposes the value via `value() -> float`.
4. Press **ESC** or click **Cancelar** → `reject()`. No changes are applied.
5. On invalid input (non-numeric), the field turns red and the dialog stays open.
6. Commas are normalised to dots before parsing (locale tolerance).

### Styling

Consistent with the screen dark theme: `#111111` background, white text, `#555555` borders. Confirm button styled green (`#1A3A1A` / `#00FF88`); cancel button uses the default dark style.

---

## Signal wiring

| Source | Mechanism | Effect |
|---|---|---|
| `vehicle_state` | 100 ms `QTimer` polling | Update top-bar values |
| `vehicle_state.emitter` | direct pyqtSignal | Reload breakpoints / VE map rows |
| Screen `keyPressEvent` | direct call | Handle ↑ / ↓ / R / O / P |
| `self._adjust_ve()` / `reset` | direct call to `_writer` | Start debounce timer |
