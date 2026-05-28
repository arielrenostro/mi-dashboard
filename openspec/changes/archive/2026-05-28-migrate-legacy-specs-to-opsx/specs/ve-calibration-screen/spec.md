## ADDED Requirements

### Requirement: Screen has three vertical zones with defined heights
The VE Calibration screen SHALL have three vertical zones separated by 1 px `#333333` dividers with no padding:
- Top bar: 80 px fixed height
- Centre: stretch (fills remaining height), split 60% table / 40% heatmap
- Footer: 40 px fixed height

#### Scenario: Layout fills available height
- **WHEN** the VE Calibration screen is activated
- **THEN** the centre zone SHALL fill all remaining height between the top bar and footer

### Requirement: Top bar displays seven signal cells
The top bar MUST show seven equally-spaced signal cells in a horizontal row: `RPM`, `MAP`, `VE`, `LAMBDA`, `LAMBDA_TARGET`, `FUEL_TRIM`, `LAMBDA_LOOP` (in that order). Cell anatomy matches the Dashboard grid but with smaller fonts:
- Signal name + unit: Arial 12 Bold, gray (`#888888`)
- Current value: Arial 40 Bold, white (`#FFFFFF`)

`LAMBDA_LOOP` special coloring: green (`#00FF00`) = Closed, orange (`#FF8800`) = Open.

Values MUST be updated every time `process_signals(parsed_data)` is called.

#### Scenario: LAMBDA_LOOP shows green when closed
- **WHEN** the LAMBDA_LOOP signal value is 1 (Closed)
- **THEN** the value SHALL be displayed in green (`#00FF00`)

### Requirement: VE map table (16×17) shows axis labels and cell values
A `QTableWidget(16, 17)` MUST be displayed. Column 0 is the MAP axis label (dark header, `#111111` background, gray text). Columns 1–16 show VE values for each RPM breakpoint. Horizontal header: `"MAP\RPM"` for col 0, then RPM axis values. Vertical header: MAP axis values.

Cell properties: Arial 10 font, default background `#1A1A1A`, white text. Header: `#111111` background, gray text, `#333333` gridlines. Selection mode: None. Editing: disabled.

#### Scenario: Header labels show axis values
- **WHEN** the VE map table is rendered
- **THEN** the column headers SHALL show `"MAP\RPM"` followed by RPM breakpoint values

### Requirement: Active interpolation cells are highlighted every 100 ms
Every 100 ms, the screen MUST read RPM and MAP from `vehicle_state`, call `ve_map_state.calculate_interpolation_weights()`, and apply a background color blend to active cells:
`cell_color = lerp(#1A1A1A, #FF6600, weight)`
Cells not in the weights dict MUST revert to `#1A1A1A`.

#### Scenario: Cell color intensity reflects interpolation weight
- **WHEN** a cell has weight 0.5 in the current operating point
- **THEN** its background SHALL be halfway between `#1A1A1A` and `#FF6600`

#### Scenario: Inactive cells revert to default background
- **WHEN** the operating point moves away from a previously active cell
- **THEN** that cell's background SHALL revert to `#1A1A1A`

### Requirement: Modified cells are shown in cyan text
Cells present in `ve_map_state.modified_cells` MUST have their text color set to `#00CCFF`. All other cells MUST use white (`#FFFFFF`). This highlight MUST be applied in the same 100 ms update cycle as the interpolation highlight.

#### Scenario: Modified cell has cyan text
- **WHEN** a cell is in `ve_map_state.modified_cells`
- **THEN** its text SHALL be displayed in `#00CCFF`

### Requirement: Heatmap displays VE values encoded as colors with an active-point scatter
A `pyqtgraph PlotWidget` heatmap (40% of centre width) MUST display VE values using a color map (CET-L1 preferred; fallback: `inferno`). X axis = RPM, Y axis = MAP kPa. A `ScatterPlotItem` MUST overlay the **weighted centroid** of active cells:
`centroid_rpm = Σ(rpm_axis[col] × weight)`, `centroid_map = Σ(map_axis[row] × weight)`
Scatter style: red fill, white border, size 12. Hidden when no active cells. Updated in the same 100 ms cycle.

#### Scenario: Centroid scatter is hidden when no active cells
- **WHEN** no interpolation weights are computed (no live data)
- **THEN** the scatter point SHALL not be visible

#### Scenario: Centroid tracks operating point
- **WHEN** RPM and MAP values place the operating point at a specific map location
- **THEN** the scatter point SHALL appear at the corresponding position on the heatmap

### Requirement: Footer shows keyboard shortcut hints
The footer SHALL display a single centered gray label (Arial 12, `#888888`, 40 px height):
`"↑ +6 VE   ↓ -6 VE   Espaço Loop Open/Closed   R Resetar   ESC Voltar"`

#### Scenario: Footer is always visible on this screen
- **WHEN** the VE Calibration screen is active
- **THEN** the footer label with keyboard hints SHALL be visible at the bottom

### Requirement: Update timer runs only while screen is active
A `QTimer` firing every 100 ms MUST be started in `on_activated()` and stopped in `on_deactivated()`.

#### Scenario: Timer stops when screen is hidden
- **WHEN** the VE Calibration screen is deactivated
- **THEN** the 100 ms update timer SHALL stop
