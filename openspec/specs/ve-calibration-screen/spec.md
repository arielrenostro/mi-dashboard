# ve-calibration-screen Specification

## Purpose

Defines the VE calibration screen where the operator watches the ECU's 16x16 VE map in real time, sees the current operating point, and edits values with the keyboard while the engine is running.

## Requirements

### Requirement: Screen layout
The screen SHALL consist of a top bar of live values, a central area with the VE table on the left (natural size) and the VE graph filling the rest, and a footer with the key hints `↑ +5 VE   ↓ -5 VE   O Open Loop   P Close Loop   R Resetar   ESC Voltar`. Zones SHALL be separated by thin dark lines on a black background.

#### Scenario: Footer hints
- **WHEN** the screen is shown
- **THEN** the footer lists the keys ↑, ↓, O, P, R and ESC

### Requirement: Live refresh cycle
While the screen is active, every 100 ms it SHALL: read RPM and MAP from the shared state; compute the interpolation weights of the operating point; refresh the table backgrounds and modified-cell text colors; refresh all table values; refresh the VE graph; refresh the top bar. If RPM or MAP has never been received, the cycle SHALL do nothing. The cycle SHALL stop when the screen is hidden.

#### Scenario: No data
- **WHEN** no RPM or MAP value has been received
- **THEN** the table and top bar are not refreshed

#### Scenario: Leaving the screen
- **WHEN** the user presses ESC
- **THEN** the refresh cycle stops

### Requirement: Top bar
The top bar SHALL show seven cards in order: RPM, MAP, VE, LAMBDA, LAMBDA_TARGET, FUEL_TRIM, LAMBDA_LOOP, each with the signal's display string. The LAMBDA_LOOP value SHALL be green when its raw value is `1` or `2` and orange otherwise.

#### Scenario: Open loop
- **WHEN** the lambda loop value is `0`
- **THEN** the LAMBDA_LOOP card is orange and reads `Open`

#### Scenario: Closed loop with correction
- **WHEN** the lambda loop value is `2`
- **THEN** the LAMBDA_LOOP card is green and reads `Closed+C`

### Requirement: VE table
The table SHALL be a non-editable, non-selectable 16x16 grid of VE cells showing raw integers. Columns SHALL be labeled with the RPM axis (ascending left to right) and rows with the MAP axis, with the highest MAP at the top. Cell backgrounds SHALL be a heatmap of the current map values from green (lowest) through yellow to dark red (highest). Cells with an interpolation weight SHALL be tinted toward orange (`#FF6600`) proportionally to the weight. Visually modified cells SHALL have cyan text (`#00CCFF`) and all others white (see design.md, Known issues, for a column exception).

#### Scenario: Active cells
- **WHEN** the operating point lies between four cells
- **THEN** those four cells are tinted orange in proportion to their weights

#### Scenario: Modified cell
- **WHEN** a cell in column 5 differs from the ECU-confirmed value
- **THEN** its text is cyan

#### Scenario: Axes arrive late
- **WHEN** RPM or MAP breakpoints are received from the ECU
- **THEN** the table headers are updated

#### Scenario: Row arrives
- **WHEN** a VE row is received from the ECU
- **THEN** that row of the table is refreshed

### Requirement: VE graph
The graph SHALL plot RPM (x) against VE percent (y, raw divided by 10). It SHALL draw one thin curve per MAP row (16 curves), colored from green for the lowest MAP row to red for the highest; one small square at every map node, gray by default and larger and tinted toward orange by weight for nodes currently interpolated; a lime dot at the live RPM and live VE signal, labeled `VE`; and a cyan dot at the live RPM and the VE λ signal, labeled `VE λ`, shown only while the lambda loop value is `1` or `2`.

#### Scenario: Closed loop
- **WHEN** the lambda loop value is `2`
- **THEN** the cyan VE λ dot is shown

#### Scenario: Open loop
- **WHEN** the lambda loop value is `0`
- **THEN** the cyan dot is hidden

### Requirement: Keyboard editing
On this screen: ↑ SHALL increase and ↓ SHALL decrease VE by 5 raw units (0.5 % VE) at the current operating point; R SHALL reset the map; ESC SHALL return to Home. ↑ and ↓ SHALL do nothing if RPM or MAP has never been received. Each ↑, ↓ or R SHALL start (restart) the write delay of the ve-write capability. Auto-repeat events SHALL NOT be ignored, so holding ↑ or ↓ repeats the edit.

#### Scenario: Increase
- **WHEN** the operating point is exactly on one cell and the user presses ↑
- **THEN** that cell increases by 5 raw units

#### Scenario: No operating point
- **WHEN** RPM was never received and the user presses ↑
- **THEN** the map is unchanged

#### Scenario: Reset
- **WHEN** the user presses R
- **THEN** all cells return to their ECU-confirmed values and a write is scheduled
