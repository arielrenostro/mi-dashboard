## Purpose

Defines how signal values are checked against their alarm limits, how long an alarm is considered firing, and how an audible alarm is played while at least one alarm is firing.

## ADDED Requirements

### Requirement: Limit evaluation
For every parsed set, the system SHALL evaluate each signal against its alarm configuration. A signal SHALL be out of range when its alarm is enabled and its value is strictly below the lower limit or strictly above the upper limit. A missing limit SHALL NOT be checked. A signal with its alarm disabled SHALL never be out of range for alarm purposes.

#### Scenario: Above upper limit
- **WHEN** RPM is `6700` and its alarm limit is 6600 with the alarm enabled
- **THEN** RPM is out of range

#### Scenario: At the limit
- **WHEN** RPM is exactly `6600`
- **THEN** RPM is not out of range

#### Scenario: Disabled alarm
- **WHEN** BOOST is `200` (limit 165, alarm disabled)
- **THEN** no alarm is raised for BOOST

### Requirement: Firing window
Each out-of-range evaluation SHALL (re)start a 2 second firing window for that signal in the shared state. An alarm SHALL remain firing until 2 seconds pass without an out-of-range evaluation, even if the value returns within limits sooner.

#### Scenario: Sustained condition
- **WHEN** a frame with RPM above its limit arrives every 100 ms
- **THEN** the RPM alarm stays firing continuously

#### Scenario: Condition ends
- **WHEN** RPM returns within limits
- **THEN** the alarm stops firing 2 seconds after the last out-of-range frame

### Requirement: Alarm onset notification
When a signal becomes out of range while it is not currently firing, the system SHALL emit a notification carrying that signal. The notification SHALL NOT be repeated while the signal keeps firing.

#### Scenario: First violation
- **WHEN** RPM goes out of range and was not firing
- **THEN** one notification for RPM is emitted

#### Scenario: Continued violation
- **WHEN** RPM stays out of range on the following frames
- **THEN** no further notification is emitted while it keeps firing

### Requirement: Audible alarm
The system SHALL poll the shared state every 100 ms. When any alarm is firing and the sound is not playing, it SHALL start playing the configured alarm sound; when no alarm is firing and the sound is playing, it SHALL stop it. If the sound reaches its end while any alarm is still firing, it SHALL play again from the start. Sound control SHALL happen on the UI thread.

#### Scenario: Alarm starts
- **WHEN** an alarm starts firing
- **THEN** the alarm sound starts within about 100 ms

#### Scenario: Looping
- **WHEN** the sound ends while an alarm is still firing
- **THEN** it restarts from the beginning

#### Scenario: Alarm ends
- **WHEN** the last firing alarm expires
- **THEN** the sound stops within about 100 ms
