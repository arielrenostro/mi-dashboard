## MODIFIED Requirements

### Requirement: Change events
Setting RPM breakpoints, MAP breakpoints, a VE row, an ignition row or the parameter block SHALL emit a typed change event carrying the new data (the breakpoint list, the row index and values, or the block values). Events SHALL be deliverable to consumers on the UI thread even when the change originates on a background thread.

#### Scenario: Breakpoints loaded
- **WHEN** the connection publishes MAP breakpoints
- **THEN** a MAP-breakpoints event with the new list is emitted

#### Scenario: Row loaded
- **WHEN** a VE row is published
- **THEN** a fuel-map event with the row index and values is emitted

#### Scenario: Ignition row loaded
- **WHEN** an ignition row is published
- **THEN** an ignition-map event with the row index and values is emitted

#### Scenario: Parameter block loaded
- **WHEN** the parameter block is published
- **THEN** a parameter-block event with the 16 values is emitted

## ADDED Requirements

### Requirement: Parameter block X02
The shared state SHALL hold the latest `#X02` parameter block as a list of 16 raw integers, or nothing when none has been received yet. Setting it SHALL be ignored unless the list has exactly 16 values; otherwise it SHALL replace the stored block. Readers SHALL get a copy, so changing what they read does not change the stored block.

#### Scenario: Never received
- **WHEN** no block has been set
- **THEN** reading the block yields nothing

#### Scenario: Wrong length
- **WHEN** a block with 15 values is set
- **THEN** the stored block is unchanged and no event is emitted

#### Scenario: Replacement
- **WHEN** a block is set after another one
- **THEN** reading yields the newer block

#### Scenario: Copy returned
- **WHEN** a reader modifies the list it got
- **THEN** the stored block is unchanged
