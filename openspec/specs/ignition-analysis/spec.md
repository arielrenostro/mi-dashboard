# ignition-analysis Specification

## Purpose

Defines how telemetry is filtered and accumulated per ignition offset during on-road tuning, how the per-scenario statistics are computed, and how the percentage differences and the best scenario are chosen.

## Requirements

### Requirement: Valid sample conditions
A telemetry set SHALL be counted as an analysis sample only when all of these hold: the analysis is not paused; the ignition map is loaded; RPM is between `ignition_tuning.rpm_min` and `ignition_tuning.rpm_max` inclusive (defaults 2900 and 3100); GEAR equals `ignition_tuning.gear` (default 5); LAMBDA_LOOP is `1` or `2`; the current offset has settled (see "Settling"); and RPM, GEAR, LAMBDA_LOOP, INJ_PULSE, MAP, PEDAL, LAMBDA, IGN and KNOCK are all present in the set. A set that fails any condition SHALL be discarded and SHALL NOT change any scenario.

#### Scenario: Inside the band
- **WHEN** RPM is 3000, GEAR is 5, LAMBDA_LOOP is 2, the analysis is running and the offset has settled
- **THEN** the set is a sample

#### Scenario: RPM outside the band
- **WHEN** RPM is 3200
- **THEN** the set is discarded

#### Scenario: Band edges
- **WHEN** RPM is 2900 or 3100
- **THEN** the set is a sample

#### Scenario: Wrong gear
- **WHEN** GEAR is 4
- **THEN** the set is discarded

#### Scenario: Open lambda loop
- **WHEN** LAMBDA_LOOP is `0`
- **THEN** the set is discarded

#### Scenario: Missing signal
- **WHEN** the set has no PEDAL value
- **THEN** the set is discarded

### Requirement: Settling
After the offset changes, samples SHALL be discarded until the changed rows have been written to the ECU and `ignition_tuning.settle_seconds` (default 5) have passed since that write. After the analysis is resumed from a pause, samples SHALL be discarded for `ignition_tuning.settle_seconds`. After the lambda loop returns to closed (LAMBDA_LOOP becomes `1` or `2` after a set where it was `0`, absent or the loop had never been seen closed), samples SHALL be discarded for `ignition_tuning.settle_seconds` from the first closed set. The lambda loop SHALL be tracked on every telemetry set, including sets discarded for another reason (wrong gear, RPM outside the band, paused). Changing the offset again while waiting SHALL restart the wait.

#### Scenario: Waiting for the write
- **WHEN** the offset was just raised and the rows have not yet been written
- **THEN** the sets are discarded

#### Scenario: Settled after the write
- **WHEN** the rows were written 5 seconds ago and no other change happened
- **THEN** the sets are samples again

#### Scenario: Offset changed again
- **WHEN** the offset is raised again 3 seconds after a write
- **THEN** sets are discarded until the new write is dispatched and 5 seconds have passed after it

#### Scenario: Resume
- **WHEN** the analysis is resumed
- **THEN** sets are discarded for 5 seconds

#### Scenario: Lambda loop closes again
- **WHEN** LAMBDA_LOOP goes from `0` to `1` and every other condition holds
- **THEN** the sets of the next 5 seconds are discarded and the following ones are samples

#### Scenario: Loop opened outside the band
- **WHEN** the lambda loop opens while RPM is outside the band and closes again while RPM is still outside the band, then RPM returns to the band
- **THEN** the sets are discarded until 5 seconds after the loop closed

### Requirement: Scenarios by offset
Samples SHALL be accumulated in one scenario per offset value, created on the first sample at that offset. Returning to an offset that already has a scenario SHALL add to the existing scenario. Scenarios SHALL be presented in ascending order of offset. Reset SHALL discard all scenarios.

#### Scenario: New offset
- **WHEN** the first sample arrives at offset `+1`
- **THEN** a scenario for `+1` exists, ordered after the scenario for `0`

#### Scenario: Return to an offset
- **WHEN** the offset goes `0`, `+1`, `0` and samples are valid at each
- **THEN** there are two scenarios and the second visit to `0` added to the first

#### Scenario: Reset
- **WHEN** the analysis is reset
- **THEN** there are no scenarios

### Requirement: Analysed time
The analysed time of a scenario SHALL be the sum of the intervals between consecutive samples of that scenario, where consecutive means at the same offset, with no discarded set between them and no more than 1 second apart (a continuous run). The first sample of a run SHALL add no time. Paused, discarded or settling periods SHALL NOT add time.

#### Scenario: Continuous samples
- **WHEN** samples arrive every 0.1 seconds for 10 seconds
- **THEN** the analysed time is 10 seconds (within one sample interval)

#### Scenario: Gap
- **WHEN** two consecutive samples of the scenario are 30 seconds apart
- **THEN** the 30 seconds are not counted

#### Scenario: Discarded set in between
- **WHEN** a set is discarded between two samples
- **THEN** the interval across it is not counted

### Requirement: Scenario statistics
For each scenario the analysis SHALL provide the mean of INJ_PULSE (in ms), MAP, PEDAL, LAMBDA and IGN over its samples, and a knock count. The knock count SHALL be the sum, over consecutive samples of the same continuous run (see Analysed time), of the increase of the KNOCK counter between them. A decrease of the KNOCK counter SHALL be treated as a counter restart and add nothing. Knock increases that happen while samples are discarded SHALL NOT be counted.

#### Scenario: Means
- **WHEN** three samples have INJ_PULSE 1.00, 1.10 and 1.20 ms
- **THEN** the mean injection time is 1.10 ms

#### Scenario: Knock counted
- **WHEN** consecutive samples carry KNOCK 40, 40, 42, 43
- **THEN** the knock count is 3

#### Scenario: Knock while discarded
- **WHEN** the KNOCK counter goes from 43 to 50 while the gear is wrong and the next sample reads 50
- **THEN** the knock count does not change

#### Scenario: Counter restart
- **WHEN** the KNOCK counter goes from 43 to 2 between consecutive samples
- **THEN** nothing is added for that step

### Requirement: Eligible scenarios
A scenario SHALL be eligible for comparison when its analysed time is at least `ignition_tuning.min_scenario_seconds` (default 20). Scenarios that are not eligible SHALL still be shown with their statistics but SHALL NOT take part in percentage differences or in choosing the best scenario.

#### Scenario: Short scenario
- **WHEN** a scenario has 12 seconds of analysed time
- **THEN** it has no percentage difference and cannot be the best

### Requirement: Percentage difference to the best
For each of INJ_PULSE, MAP and PEDAL, the best value SHALL be the lowest mean among eligible scenarios (lower is better for all three). The difference of an eligible scenario SHALL be `(mean - best) / best * 100` in percent, so the best scenario of that sensor shows 0. If the best value is 0, no percentage SHALL be produced for that sensor.

#### Scenario: Difference
- **WHEN** eligible scenarios have mean MAP 46.0 and 47.0
- **THEN** the first shows 0.0 % and the second shows 2.2 %

#### Scenario: Each sensor has its own best
- **WHEN** the lowest MAP belongs to one scenario and the lowest PEDAL to another
- **THEN** each sensor's percentages are relative to its own lowest mean

### Requirement: Best scenario
The best scenario SHALL be the eligible scenario with the lowest mean INJ_PULSE. Ties SHALL go to the scenario with the lower offset. There SHALL be no best scenario unless at least two scenarios are eligible. MAP and PEDAL SHALL NOT influence the choice.

#### Scenario: Lowest injection time wins
- **WHEN** two eligible scenarios have mean INJ_PULSE 1.10 and 1.08 ms
- **THEN** the second is the best

#### Scenario: Single eligible scenario
- **WHEN** only one scenario is eligible
- **THEN** there is no best scenario

#### Scenario: Tie
- **WHEN** offsets `+1` and `+2` have the same lowest mean injection time
- **THEN** `+1` is the best

### Requirement: Pause and resume
The analysis SHALL be pausable and resumable. While paused, no set SHALL be counted, and the offset MAY still be changed. Pausing and resuming SHALL NOT change any scenario.

#### Scenario: Paused
- **WHEN** the analysis is paused and a valid set arrives
- **THEN** no scenario changes

#### Scenario: Offset change while paused
- **WHEN** the analysis is paused and the offset is raised
- **THEN** the offset changes and no scenario is created until the analysis resumes and samples are valid

### Requirement: Scenario ready notification
When the analysed time of the scenario at the current offset reaches `ignition_tuning.min_scenario_seconds`, the analysis SHALL notify once. It SHALL notify again only if the scenario falls below the threshold (which can only happen after a reset) and reaches it again.

#### Scenario: Threshold reached
- **WHEN** the current scenario goes from 19.9 to 20.0 seconds
- **THEN** one notification is raised

#### Scenario: Beyond the threshold
- **WHEN** the current scenario keeps accumulating after 20 seconds
- **THEN** no further notification is raised

### Requirement: Discard the worst scenario
The analysis SHALL be able to discard the worst scenario: the eligible scenario with the highest mean INJ_PULSE (ties go to the lower offset). It SHALL discard nothing when fewer than two scenarios are eligible, and nothing when the worst scenario is the one of the current offset (no other scenario is discarded in its place). Discarding SHALL remove only the accumulated data of that scenario: the offset and the ignition map are unchanged, and returning to that offset later SHALL start a new scenario from zero. The result SHALL tell whether a scenario was discarded.

#### Scenario: Worst discarded
- **WHEN** eligible scenarios at offsets `0`, `+1`, `+2` have mean injection time 1.12, 1.10 and 1.08 ms and the current offset is `+2`
- **THEN** the scenario at `0` is discarded and the other two remain

#### Scenario: Worst is the current one
- **WHEN** the scenario of the current offset has the highest mean injection time
- **THEN** nothing is discarded

#### Scenario: Fewer than two eligible
- **WHEN** only one scenario is eligible
- **THEN** nothing is discarded

#### Scenario: Not eligible scenarios are never the worst
- **WHEN** a scenario with little analysed time has the highest mean injection time
- **THEN** it is not discarded, and the worst eligible scenario is

#### Scenario: Tie
- **WHEN** offsets `0` and `+1` share the highest mean injection time
- **THEN** the scenario at `0` is discarded

#### Scenario: Returning to a discarded offset
- **WHEN** the scenario at `+1` was discarded and samples are later valid at `+1` again
- **THEN** a new scenario for `+1` exists with only the new samples

#### Scenario: Repeated
- **WHEN** the user discards repeatedly
- **THEN** scenarios are discarded one by one until fewer than two are eligible or the worst is the current one
