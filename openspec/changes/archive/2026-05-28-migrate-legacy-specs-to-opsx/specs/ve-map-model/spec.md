## ADDED Requirements

### Requirement: VeMapState holds a 16×16 VE map indexed by MAP row and RPM column
The system SHALL maintain a 16×16 in-memory VE map. Cell addressing: `ve_map[row][col]` where `row` = MAP axis index (0 = lowest pressure), `col` = RPM axis index (0 = lowest RPM). Values SHALL be `float` in the range `[0.0, 1999.9]`. Initial value for all cells SHALL be `100.0`. A module-level singleton `ve_map_state = VeMapState()` MUST be available.

Default RPM axis (16 values): `[500, 750, 1000, 1250, 1500, 1750, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]`
Default MAP axis (16 values): `[10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160]`

#### Scenario: Default cell value is 100.0
- **WHEN** `VeMapState` is initialized without ECU data
- **THEN** every cell `ve_map[r][c]` SHALL equal `100.0`

### Requirement: Cell set clamps value and tracks modifications
`set_cell(row, col, value)` MUST clamp the value to `[0, 1999.9]`. A cell MUST be added to `modified_cells` when `|new_value − original_value| > 0.05`. It MUST be removed from `modified_cells` when the value returns within that tolerance.

#### Scenario: Value is clamped at maximum
- **WHEN** `set_cell(0, 0, 2500.0)` is called
- **THEN** the stored value SHALL be `1999.9`

#### Scenario: Cell enters modified_cells when changed significantly
- **WHEN** a cell's original value is `100.0` and `set_cell` writes `106.1`
- **THEN** that cell SHALL be in `modified_cells`

#### Scenario: Cell leaves modified_cells when restored
- **WHEN** a modified cell is set back to a value within 0.05 of the original
- **THEN** that cell SHALL be removed from `modified_cells`

### Requirement: Bilinear interpolation computes weights for up to 4 surrounding cells
`calculate_interpolation_weights(rpm, map_val)` MUST locate the four surrounding breakpoints using `bisect.bisect_right` and compute weights as:
```
t_rpm = (rpm − rpm_axis[col1]) / (rpm_axis[col2] − rpm_axis[col1])
t_map = (map − map_axis[row1]) / (map_axis[row2] − map_axis[row1])

w[row1][col1] = (1 − t_map) × (1 − t_rpm)
w[row1][col2] = (1 − t_map) × t_rpm
w[row2][col1] = t_map       × (1 − t_rpm)
w[row2][col2] = t_map       × t_rpm
```
Weights MUST sum to 1.0. Cells with weight < 0.001 SHALL be omitted. When `col1 == col2` or `row1 == row2`, duplicate keys SHALL be collapsed by summing their weights.

Edge clamping: rpm ≤ rpm_axis[0] → col1=col2=0, t_rpm=0; rpm ≥ rpm_axis[-1] → col1=col2=15, t_rpm=0; same pattern for MAP.

#### Scenario: Weights sum to 1.0 for interior operating point
- **WHEN** RPM and MAP fall strictly between two breakpoints each
- **THEN** the sum of all returned weights SHALL be 1.0

#### Scenario: Edge clamping yields single active cell
- **WHEN** RPM is below `rpm_axis[0]` and MAP is below `map_axis[0]`
- **THEN** only cell `(0, 0)` SHALL be in the result with weight 1.0

### Requirement: adjust_ve distributes delta proportionally across active cells
`adjust_ve(rpm, map_val, delta)` MUST compute interpolation weights, then for each active cell apply `new_value = current_value + delta × weight`. The total effective VE change SHALL equal `delta`.

#### Scenario: Delta is fully distributed
- **WHEN** `adjust_ve` is called with delta=6.0 and two active cells each with weight 0.5
- **THEN** each cell's value SHALL increase by 3.0

### Requirement: reset restores all cells to original values
`reset()` MUST copy all values from `original_ve_map` back to `ve_map` and clear `modified_cells`.

#### Scenario: Reset clears all modifications
- **WHEN** several cells have been edited and `reset()` is called
- **THEN** all cells SHALL equal their original values and `modified_cells` SHALL be empty

### Requirement: load_from_ecu replaces axes and map
`load_from_ecu(rpm_axis, map_axis, ve_map)` MUST replace both axis arrays, the full map, and reset `modified_cells`. The loaded map becomes the new `original_ve_map`.

#### Scenario: ECU data replaces defaults
- **WHEN** `load_from_ecu` is called with new axes and map
- **THEN** `calculate_interpolation_weights` SHALL use the new axes
