## ADDED Requirements

### Requirement: Inclination condition
When `gyro.port` is not empty, the inclinometer is required: in addition to every condition of "Valid sample conditions", a telemetry set SHALL be counted as an analysis sample only while the inclination is usable (see `gyro-connection`, "Usable pitch") and the absolute value of the usable pitch is at most `ignition_tuning.max_tilt_deg` (default 3, inclusive). A set that fails this condition SHALL be discarded and SHALL NOT change any scenario. The roll SHALL NOT be considered. The condition SHALL be evaluated with the latest pitch at the moment of every telemetry set, and also when the inclinometer stops being usable in the middle of a run. When `gyro.port` is empty the condition SHALL NOT exist and the pitch SHALL be ignored.

#### Scenario: Level
- **WHEN** the inclinometer is required and usable, the pitch is 1.2, `max_tilt_deg` is 3 and every other condition holds
- **THEN** the set is a sample

#### Scenario: Limit is inclusive
- **WHEN** the pitch is 3.0 or -3.0 and `max_tilt_deg` is 3
- **THEN** the set is a sample

#### Scenario: Uphill or downhill
- **WHEN** the pitch is -4.2 or 4.2 and `max_tilt_deg` is 3
- **THEN** the set is discarded

#### Scenario: Not zeroed
- **WHEN** `gyro.port` is set and the device is connected but not zeroed
- **THEN** the set is discarded

#### Scenario: Sensor lost in the middle of a run
- **WHEN** samples were being accepted and the inclinometer becomes `no signal`
- **THEN** the following sets are discarded until it is usable and level again

#### Scenario: Roll ignored
- **WHEN** the pitch is 0.5 and the roll is 10
- **THEN** the inclination condition holds

#### Scenario: Sensor not configured
- **WHEN** `gyro.port` is empty and every other condition holds
- **THEN** the set is a sample, whatever the inclinometer would report

### Requirement: Settling after the inclination is usable and level
When the inclination condition goes from not holding to holding (the inclinometer becomes usable with a pitch within the limit, or the pitch comes back within the limit), samples SHALL be discarded for `ignition_tuning.settle_seconds` from the first set where it holds. The condition SHALL be tracked on every telemetry set, including sets discarded for another reason (wrong gear, RPM outside the band, paused), so the first set after the app starts that finds the inclination usable and level also starts the wait. While the inclinometer is not required nothing SHALL be tracked. A pitch that crosses the limit again while waiting SHALL restart the wait when it comes back.

#### Scenario: Level again
- **WHEN** the pitch was 5 and the set at time T has pitch 1 with every other condition holding
- **THEN** the sets of the next 5 seconds are discarded and the following ones are samples

#### Scenario: First usable reading
- **WHEN** the device has just been zeroed and the pitch is within the limit
- **THEN** the sets of the next 5 seconds are discarded

#### Scenario: Tracked while another condition fails
- **WHEN** the inclination becomes usable and level while RPM is outside the band, and RPM enters the band 2 seconds later
- **THEN** the sets are discarded for the remaining 3 seconds

#### Scenario: Crossing again
- **WHEN** the pitch is within the limit for 3 seconds after being outside, goes outside the limit and comes back
- **THEN** the wait of 5 seconds starts again from the moment it comes back

#### Scenario: Not required
- **WHEN** `gyro.port` is empty and the pitch changes
- **THEN** no wait starts

### Requirement: Settings applied while running
Changes of `ignition_tuning.rpm_min`, `ignition_tuning.rpm_max`, `ignition_tuning.settle_seconds`, `ignition_tuning.min_scenario_seconds` and `ignition_tuning.max_tilt_deg` made while the app runs SHALL be used from the next telemetry set or query, without restarting the app. A change of `rpm_min` or `rpm_max` SHALL discard the scenarios of every gear (as a reset of the scenarios does), because scenarios of different bands are not comparable; it SHALL NOT change the offset nor write anything to the ECU. A change of the other settings SHALL NOT discard scenarios.

#### Scenario: Band changed
- **WHEN** scenarios exist and `rpm_max` changes from 3100 to 3200
- **THEN** every scenario is discarded and the set at RPM 3150 is a sample from then on

#### Scenario: Settle time changed
- **WHEN** `settle_seconds` changes from 5 to 8 and the offset is changed afterwards
- **THEN** the wait after the write is 8 seconds and no scenario was discarded by the change

#### Scenario: Tilt limit changed
- **WHEN** `max_tilt_deg` changes from 3 to 5 and the pitch is 4
- **THEN** the inclination condition holds
