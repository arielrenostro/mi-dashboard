# ve-map-model Specification

## Purpose

Defines the in-memory 16x16 volumetric efficiency (VE) map used for calibration: raw units, axes, bilinear interpolation weights for the current operating point, and how edits, modification tracking and reset behave.

## Requirements

### Requirement: Raw VE units and addressing
VE values SHALL be stored as raw ECU integers where VE percent equals raw divided by 10 (for example `855` is 85.5 %). A cell SHALL be addressed by `[row][col]` where `row` is the MAP axis index (0 = lowest MAP) and `col` is the RPM axis index (0 = lowest RPM). Before ECU data is loaded, every cell SHALL be `1000` (100.0 %) in both the working map and the ECU-confirmed original map.

#### Scenario: Placeholder values
- **WHEN** no VE row has been received
- **THEN** every cell reads `1000`

### Requirement: Axes
The RPM axis and the MAP axis SHALL be loaded from the ECU breakpoints and SHALL be ascending lists of 16 integers. A breakpoint list that does not contain exactly 16 values SHALL be ignored. The app SHALL NOT modify the axes.

#### Scenario: Axis loaded
- **WHEN** 16 RPM breakpoints are received
- **THEN** they become the RPM axis

#### Scenario: Wrong size
- **WHEN** a list with 15 values is received
- **THEN** the existing axis is kept

### Requirement: Loading a row from the ECU
When a VE row is received from the ECU, every cell of that row SHALL be replaced in both the working map and the ECU-confirmed original map, discarding any unsent edit in that row. Rows with fewer than 16 values or an out-of-range index SHALL be ignored.

#### Scenario: Row replaces edits
- **WHEN** a row containing edited cells is received again from the ECU
- **THEN** its cells equal the received values and are no longer considered modified

### Requirement: Interpolation weights
Given the current RPM and MAP, the model SHALL return the weights of up to four cells using bilinear interpolation between the surrounding axis breakpoints. The lower breakpoint index is the last one not greater than the value; `t` is the fractional position between lower and upper breakpoint. Cell weights are `(1-t_map)(1-t_rpm)`, `(1-t_map)t_rpm`, `t_map(1-t_rpm)` and `t_map*t_rpm`. Values at or below the first breakpoint SHALL use index 0 only, and values at or above the last breakpoint SHALL use index 15 only. Weights below 0.001 SHALL be omitted, and weights that land on the same cell SHALL be summed. If either axis is empty the result SHALL be empty.

#### Scenario: Between four cells
- **WHEN** RPM and MAP are each halfway between two breakpoints
- **THEN** four cells each have weight 0.25

#### Scenario: Exactly on a breakpoint
- **WHEN** RPM equals an axis value and MAP is halfway between two breakpoints
- **THEN** two cells each have weight 0.5

#### Scenario: Above the last breakpoint
- **WHEN** RPM is above the last RPM breakpoint
- **THEN** only column 15 receives weight

### Requirement: Adjusting at the operating point
Adjusting by a delta (in raw units) at an RPM and MAP SHALL add `delta * weight` to each cell with a weight, rounding each resulting cell to an integer and clamping it to the range 0 to 19999. A cell whose share rounds to no change SHALL remain unchanged.

#### Scenario: Single cell
- **WHEN** the operating point is exactly on a cell and the delta is +5
- **THEN** that cell increases by 5 raw units

#### Scenario: Split between two cells
- **WHEN** two cells each have weight 0.5 and the delta is +5
- **THEN** each cell receives +2.5 before rounding

#### Scenario: Upper clamp
- **WHEN** a cell would exceed 19999
- **THEN** it becomes 19999

### Requirement: Modification tracking
After each cell write, the cell SHALL be added to the set of pending cells when its value differs from the ECU-confirmed original value, and removed when it equals the original. The set of visually modified cells SHALL be all cells whose working value differs from the original value, including cells whose row was already sent to the ECU. The pending rows SHALL be the sorted distinct row indices of the pending cells. After a row is marked as sent, its cells SHALL be removed from the pending set but remain visually modified.

#### Scenario: Edit then undo
- **WHEN** a cell is raised by 5 and then lowered by 5
- **THEN** it is no longer pending nor visually modified

#### Scenario: Sent row
- **WHEN** a pending row is marked as sent
- **THEN** it is no longer pending but its edited cells remain visually modified

### Requirement: Reset
Resetting SHALL restore every cell of the working map to the ECU-confirmed original value and SHALL mark every row as pending (so that all 16 rows are written back to the ECU by the write cycle), while no cell is reported as visually modified.

#### Scenario: Reset after edits
- **WHEN** the user resets after editing some cells
- **THEN** the working map equals the original map and all 16 rows are pending
