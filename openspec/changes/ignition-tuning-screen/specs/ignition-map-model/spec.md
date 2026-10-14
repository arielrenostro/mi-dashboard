## Purpose

Defines the in-memory 16x16 ignition map used for on-road tuning: the ECU-confirmed original map, one global advance offset, the derived working map, which rows the offset applies to, clamping, pending rows and reset.

## ADDED Requirements

### Requirement: Raw ignition units and addressing
Ignition values SHALL be stored as raw ECU integers in whole degrees of advance. A cell SHALL be addressed by `[row][col]` where `row` is the MAP axis index (0 = lowest MAP) and `col` is the RPM axis index (0 = lowest RPM), the same addressing as the VE map. The model SHALL use the MAP and RPM axes loaded from the ECU and SHALL NOT modify them.

#### Scenario: Addressing
- **WHEN** ignition row `#I01` is received
- **THEN** its values are the cells of the lowest-MAP row

### Requirement: Loading an ignition row
When an ignition row is received from the ECU while the offset is `0`, every cell of that row SHALL be replaced in the original map and the working map. Rows with fewer than 16 values or an out-of-range index SHALL be ignored. While the offset is not `0`, or while a row's values written (or still to be written) to the ECU differ from its original, received rows SHALL be ignored, because the ECU then holds values this tool wrote and they are not the original. The model SHALL report the map as loaded only after all 16 rows have been received.

#### Scenario: Row received at offset 0
- **WHEN** a row is received while the offset is `0`
- **THEN** the original and working cells of that row equal the received values

#### Scenario: Row received while an offset is applied
- **WHEN** a row is received while the offset is `+2`
- **THEN** the original map is unchanged

#### Scenario: Row received while a write is outstanding
- **WHEN** the offset went from `+1` back to `0` but the original values were not written yet, and a row is received
- **THEN** the original map is unchanged

#### Scenario: Not loaded yet
- **WHEN** only 15 of the 16 rows have been received
- **THEN** the map is reported as not loaded

### Requirement: Global advance offset
The model SHALL keep one integer offset, initially `0`, that is the number of degrees added to the original map. The working map SHALL always be computed from the original map and the offset, never from the previous working map: for every cell of an affected row the working value SHALL be `max(0, min(ceiling, original + offset))`, where `ceiling` is `ignition_tuning.max_ignition` (default 50). Cells of unaffected rows SHALL equal the original, and at offset `0` the whole working map SHALL equal the original, whatever the ceiling. Raising or lowering the offset by 1 SHALL change the offset only when the map is loaded; otherwise the offset SHALL stay `0`.

#### Scenario: Raise
- **WHEN** the offset goes from `0` to `+1`
- **THEN** every cell of the affected rows is its original value plus 1

#### Scenario: Lower
- **WHEN** the offset goes from `0` to `-1`
- **THEN** every cell of the affected rows is its original value minus 1, with a minimum of 0

#### Scenario: Floor and recovery
- **WHEN** a cell with original value 2 is lowered to offset `-5` and the offset is then raised back to `-1`
- **THEN** the cell is 0 at `-5` and 1 at `-1`, not 0

#### Scenario: Ceiling
- **WHEN** a cell with original value 49 is raised to offset `+3`
- **THEN** the cell is 50

#### Scenario: Offset zero is the original
- **WHEN** a cell has original value 55, above the ceiling, and the offset is `0`
- **THEN** the cell is 55

#### Scenario: Map not loaded
- **WHEN** the offset is raised before all 16 rows were received
- **THEN** the offset stays `0` and the working map is unchanged

### Requirement: Rows affected by the offset
The offset SHALL apply to every column of each row whose MAP axis value is less than or equal to `ignition_tuning.max_map_kpa` (default 70). Rows whose MAP axis value is greater SHALL always keep their original values. If the MAP axis has not been loaded (all zeros), the offset SHALL NOT change.

#### Scenario: Limit row included
- **WHEN** the MAP axis contains 70 and the offset is `+1`
- **THEN** the row at 70 kPa is changed in all 16 columns

#### Scenario: Rows above the limit
- **WHEN** the MAP axis contains 80 and the limit is 70
- **THEN** the row at 80 kPa equals its original values at any offset

#### Scenario: Axis not loaded
- **WHEN** the MAP axis is all zeros and Up is pressed
- **THEN** the offset stays `0`

### Requirement: Pending rows
After the offset changes, the model SHALL mark as pending every row of the working map that differs from the last row values handed to the writer (initially the original values). The pending rows SHALL be the sorted row indices. Marking a row as sent SHALL record its current working values as the last written values and remove it from the pending set.

#### Scenario: Raise by one
- **WHEN** the offset goes from `0` to `+1` and the MAP limit covers rows 0 to 5
- **THEN** rows 0 to 5 are pending, and rows 6 to 15 are not

#### Scenario: Sent rows
- **WHEN** the pending rows are marked as sent
- **THEN** no row is pending until the offset changes again

#### Scenario: Undone before sending
- **WHEN** the offset goes to `+1` and back to `0` before any row is sent
- **THEN** no row is pending

### Requirement: Reset
Resetting SHALL set the offset to `0`, restore the working map to the original map, and mark all 16 rows as pending, so the next write puts the original values of every row back in the ECU (the same convention as the VE map reset). Reset SHALL work even when the map is not loaded, in which case it only clears the offset.

#### Scenario: Reset after edits
- **WHEN** the offset is `+3` and the changes were sent, then the model is reset
- **THEN** the offset is `0`, the working map equals the original, and all 16 rows are pending

#### Scenario: Reset without a loaded map
- **WHEN** the map is not loaded and the model is reset
- **THEN** the offset is `0` and no row is pending
