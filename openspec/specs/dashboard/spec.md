# dashboard Specification

## Purpose

Defines the Dashboard screen: a configurable grid of live numeric values on top and configurable live graphs with peak and minimum markers below.

## Requirements

### Requirement: Layout
The Dashboard SHALL fill the window with a numeric grid above and the graph plots below, stacked vertically with a small gap.

#### Scenario: Default arrangement
- **WHEN** the Dashboard is shown with the default configuration
- **THEN** a 2-row grid appears on top and two plots appear below it

### Requirement: Numeric grid
The grid SHALL contain one card per signal name in the configured `dashboard.grid`, placed at the same row and column as in the configuration. Each card SHALL show a small gray bold label `"<name> (<unit>)"` (or `"<name>"` when the unit is empty) at the top left, and the current value in large bold text at the right. Before any value arrives a card SHALL show `--`. The value text SHALL be the signal's display string and its color SHALL be the signal's color.

#### Scenario: Card with unit
- **WHEN** the grid contains CLT
- **THEN** the label reads `CLT (ºC)`

#### Scenario: Card without unit
- **WHEN** the grid contains GEAR
- **THEN** the label reads `Gear`

#### Scenario: No data yet
- **WHEN** no frame has arrived
- **THEN** every card shows `--`

### Requirement: Live update
Every time a parsed set arrives, each card whose signal is present in the set SHALL update its value, whether or not the Dashboard is the visible screen.

#### Scenario: New frame
- **WHEN** a frame with RPM `3415` arrives
- **THEN** the RPM card shows `3415`

### Requirement: Out-of-limit color for non-alarm signals
For a signal whose alarm is not enabled but whose catalog entry has limits, the card value SHALL be shown in red while the value is strictly outside those limits, and in the signal's color otherwise. For signals with the alarm enabled, the card color SHALL NOT be changed by this update path (see design.md, Known issues).

#### Scenario: Boost above its limit
- **WHEN** BOOST is `200` (limit 165, alarm disabled)
- **THEN** the BOOST card value is red

#### Scenario: Back within limits
- **WHEN** BOOST returns to `150`
- **THEN** the card value returns to the BOOST color

### Requirement: Graph groups
The Dashboard SHALL create one plot per group in `dashboard.graph`, each containing one curve per signal in that group. Each plot SHALL show no left and no bottom axis; each signal SHALL have its own right-hand axis labeled with the signal name in the signal color, scaled to the signal's graph range. The horizontal range SHALL be fixed to the configured number of samples and the horizontal axis SHALL NOT be pannable or zoomable; vertical interaction SHALL remain enabled. Curves SHALL be 2 px wide in the signal color.

#### Scenario: Multi-axis plot
- **WHEN** a group contains LAMBDA, LAMBDA_TARGET and FUEL_TRIM
- **THEN** one plot with three curves and three right-hand axes is shown

### Requirement: Graph data buffers
For every graphed signal the system SHALL keep the latest `dashboard.graph_x_size` values, appending one value per received frame that contains the signal and discarding the oldest when full. Buffers SHALL keep filling while the Dashboard is not visible. Curves SHALL be redrawn every 100 ms only while the Dashboard is the active screen.

#### Scenario: Buffer full
- **WHEN** `graph_x_size` is 150 and the 151st value arrives
- **THEN** the oldest value is dropped

#### Scenario: Screen hidden
- **WHEN** the user is on another screen
- **THEN** curves are not redrawn, and on return they show the most recent buffered data

### Requirement: Peak and minimum markers
For each graphed signal with at least one buffered value, the plot SHALL show a circular marker (size 10, signal color, white 2 px border) at the position of the buffer's maximum and another at its minimum, each with a bold label in the signal color showing the display string of that value followed by the unit (no unit text when the unit is empty). When the buffer is empty the markers and labels SHALL be hidden. When several samples share the extreme value, the first occurrence SHALL be used.

#### Scenario: Peak label
- **WHEN** the highest buffered RPM is `5200`
- **THEN** a marker with label `5200 RPM` is placed at that sample

#### Scenario: Empty buffer
- **WHEN** no value has been buffered for a signal
- **THEN** its markers and labels are hidden

### Requirement: Dashboard keys
Pressing ESC on the Dashboard SHALL return to the Home screen. No other key SHALL have an effect on the Dashboard.

#### Scenario: Back to Home
- **WHEN** the user presses ESC on the Dashboard
- **THEN** the Home screen is shown
