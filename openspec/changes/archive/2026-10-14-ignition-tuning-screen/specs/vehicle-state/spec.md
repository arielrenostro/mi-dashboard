## MODIFIED Requirements

### Requirement: Axis breakpoints and VE map
The shared state SHALL hold 16 RPM breakpoints, 16 MAP breakpoints, a 16x16 VE map and a 16x16 ignition map of raw integers, all initially zero. Setting breakpoints SHALL replace the list. Setting a VE row or an ignition row SHALL be ignored unless it has exactly 16 values; otherwise it SHALL replace the row at the given index.

#### Scenario: Wrong row length
- **WHEN** a VE row with 15 values is set
- **THEN** the map is unchanged and no event is emitted

#### Scenario: Wrong ignition row length
- **WHEN** an ignition row with 15 values is set
- **THEN** the ignition map is unchanged and no event is emitted

### Requirement: Change events
Setting RPM breakpoints, MAP breakpoints, a VE row or an ignition row SHALL emit a typed change event carrying the new data (the breakpoint list, or the row index and values). Events SHALL be deliverable to consumers on the UI thread even when the change originates on a background thread.

#### Scenario: Breakpoints loaded
- **WHEN** the connection publishes MAP breakpoints
- **THEN** a MAP-breakpoints event with the new list is emitted

#### Scenario: Row loaded
- **WHEN** a VE row is published
- **THEN** a fuel-map event with the row index and values is emitted

#### Scenario: Ignition row loaded
- **WHEN** an ignition row is published
- **THEN** an ignition-map event with the row index and values is emitted
