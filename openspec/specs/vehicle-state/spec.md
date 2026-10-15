# vehicle-state Specification

## Purpose

Defines the shared, thread-safe snapshot of the vehicle and ECU data (latest signals, alarm timestamps, axis breakpoints, VE map) that background and UI parts of the app read and write, and the change events it emits.

## Requirements

### Requirement: Latest signal snapshot
The shared state SHALL keep the most recent parsed value of every signal. Publishing a parsed set SHALL replace the stored value of each signal present in the set and leave other signals unchanged. Readers SHALL be able to get one signal (or nothing if never received) and a copy of the whole snapshot.

#### Scenario: Merge
- **WHEN** a set containing only RPM is published after a set containing RPM and MAP
- **THEN** RPM has the new value and MAP keeps its previous value

#### Scenario: Never received
- **WHEN** a signal has never been published
- **THEN** reading it yields nothing

### Requirement: Alarm timestamps
The shared state SHALL record the time of the last out-of-range report for each signal. A signal SHALL be reported as firing when its last report is less than 2 seconds old, and "any alarm firing" SHALL be true when at least one signal is firing. Reporting a signal as not out of range SHALL NOT clear an existing timestamp.

#### Scenario: Firing window
- **WHEN** a signal was reported out of range 1.5 seconds ago and not since
- **THEN** it is still firing

#### Scenario: Window elapsed
- **WHEN** the last report is 2 seconds old or older
- **THEN** it is not firing

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

### Requirement: Thread safety
All reads and writes of the shared state SHALL be mutually exclusive so that background and UI threads can use it concurrently.

#### Scenario: Concurrent access
- **WHEN** the connection thread publishes a row while the UI thread reads signals
- **THEN** neither observes a partially updated signal map
