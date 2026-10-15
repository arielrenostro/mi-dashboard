## RENAMED Requirements

- FROM: `### Requirement: Scenarios by offset`
- TO: `### Requirement: Scenarios by gear and offset`

## MODIFIED Requirements

### Requirement: Valid sample conditions
A telemetry set SHALL be counted as an analysis sample only when all of these hold: the analysis is not paused; the ignition map is loaded; RPM is between `ignition_tuning.rpm_min` and `ignition_tuning.rpm_max` inclusive (defaults 2900 and 3100); GEAR equals one of the gears in `ignition_tuning.gears` (default `[5]`); LAMBDA_LOOP is `1` or `2`; the current offset has settled (see "Settling"); and RPM, GEAR, LAMBDA_LOOP, INJ_PULSE, MAP, PEDAL, LAMBDA, IGN and KNOCK are all present in the set. A set that fails any condition SHALL be discarded and SHALL NOT change any scenario.

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
- **WHEN** the gears are `[5]` and GEAR is 4
- **THEN** the set is discarded

#### Scenario: Second configured gear
- **WHEN** the gears are `[4, 5]`, GEAR is 4 and every other condition holds
- **THEN** the set is a sample

#### Scenario: Gear not configured
- **WHEN** the gears are `[4, 5]` and GEAR is 3
- **THEN** the set is discarded

#### Scenario: Open lambda loop
- **WHEN** LAMBDA_LOOP is `0`
- **THEN** the set is discarded

#### Scenario: Missing signal
- **WHEN** the set has no PEDAL value
- **THEN** the set is discarded

### Requirement: Scenarios by gear and offset
Samples SHALL be accumulated in one scenario per gear and offset value, created on the first sample with that gear and offset. The advance offset is global, so one offset applies to every gear. Returning to a gear and offset that already have a scenario SHALL add to the existing scenario. Changing gear SHALL NOT start settling: the first set in the new gear that satisfies the other conditions is a sample. Scenarios SHALL be presented per gear, in ascending order of offset, and the analysis SHALL tell which gears hold at least one scenario. Reset SHALL discard the scenarios of every gear.

#### Scenario: New offset
- **WHEN** the first sample in gear 5 arrives at offset `+1`
- **THEN** a scenario for gear 5 and `+1` exists, ordered after the scenario for gear 5 and `0`

#### Scenario: Return to an offset
- **WHEN** the offset goes `0`, `+1`, `0` and samples in gear 5 are valid at each
- **THEN** gear 5 has two scenarios and the second visit to `0` added to the first

#### Scenario: Same offset in two gears
- **WHEN** valid samples arrive at offset `+1` in gear 4 and in gear 5
- **THEN** gear 4 and gear 5 each have their own scenario for `+1`, with separate statistics

#### Scenario: Gear change without settling
- **WHEN** the gears are `[4, 5]`, the analysis was sampling in gear 5, the lambda loop stays closed and the next set is in gear 4 inside the band
- **THEN** that set is a sample of gear 4

#### Scenario: Gears holding data
- **WHEN** only gear 5 has scenarios
- **THEN** gear 5 is reported as holding data and gear 4 is not

#### Scenario: Reset
- **WHEN** the analysis is reset
- **THEN** no gear has scenarios

### Requirement: Analysed time
The analysed time of a scenario SHALL be the sum of the intervals between consecutive samples of that scenario, where consecutive means at the same gear and offset, with no discarded set between them and no more than 1 second apart (a continuous run). The first sample of a run SHALL add no time. Paused, discarded or settling periods SHALL NOT add time.

#### Scenario: Continuous samples
- **WHEN** samples arrive every 0.1 seconds for 10 seconds
- **THEN** the analysed time is 10 seconds (within one sample interval)

#### Scenario: Gap
- **WHEN** two consecutive samples of the scenario are 30 seconds apart
- **THEN** the 30 seconds are not counted

#### Scenario: Discarded set in between
- **WHEN** a set is discarded between two samples
- **THEN** the interval across it is not counted

#### Scenario: Gear change ends the run
- **WHEN** consecutive samples are in gear 5 and then in gear 4 and then in gear 5 again, 0.1 seconds apart
- **THEN** no interval across a gear change is added to any scenario and the knock counter is not compared across it

### Requirement: Percentage difference to the best
Within each gear, for each of INJ_PULSE, MAP and PEDAL, the best value SHALL be the lowest mean among the eligible scenarios of that gear (lower is better for all three). The difference of an eligible scenario SHALL be `(mean - best) / best * 100` in percent, so the best scenario of that sensor shows 0. If the best value is 0, no percentage SHALL be produced for that sensor. Scenarios of different gears SHALL NOT be compared with each other.

#### Scenario: Difference
- **WHEN** eligible scenarios of one gear have mean MAP 46.0 and 47.0
- **THEN** the first shows 0.0 % and the second shows 2.2 %

#### Scenario: Each sensor has its own best
- **WHEN** the lowest MAP belongs to one scenario and the lowest PEDAL to another, in the same gear
- **THEN** each sensor's percentages are relative to its own lowest mean

#### Scenario: Gears are independent
- **WHEN** gear 4 has eligible scenarios with mean MAP 60.0 and 61.0 and gear 5 has eligible scenarios with mean MAP 46.0 and 47.0
- **THEN** the second scenario of gear 4 shows 1.7 % and the second of gear 5 shows 2.2 %

### Requirement: Best scenario
Within each gear, the best scenario SHALL be the eligible scenario with the lowest mean INJ_PULSE. Ties SHALL go to the scenario with the lower offset. A gear SHALL have no best scenario unless at least two of its scenarios are eligible. MAP and PEDAL SHALL NOT influence the choice.

#### Scenario: Lowest injection time wins
- **WHEN** two eligible scenarios of one gear have mean INJ_PULSE 1.10 and 1.08 ms
- **THEN** the second is the best of that gear

#### Scenario: Single eligible scenario
- **WHEN** only one scenario of a gear is eligible
- **THEN** that gear has no best scenario

#### Scenario: Tie
- **WHEN** offsets `+1` and `+2` of one gear have the same lowest mean injection time
- **THEN** `+1` is the best of that gear

#### Scenario: One best per gear
- **WHEN** gear 4 and gear 5 each have two eligible scenarios
- **THEN** each gear has its own best scenario

### Requirement: Scenario ready notification
When the analysed time of the scenario of the gear being sampled and the current offset reaches `ignition_tuning.min_scenario_seconds`, the analysis SHALL notify once. It SHALL notify again for that scenario only if it falls below the threshold (which can only happen after a reset) and reaches it again.

#### Scenario: Threshold reached
- **WHEN** the current scenario goes from 19.9 to 20.0 seconds
- **THEN** one notification is raised

#### Scenario: Beyond the threshold
- **WHEN** the current scenario keeps accumulating after 20 seconds
- **THEN** no further notification is raised

#### Scenario: Threshold reached in the other gear
- **WHEN** the scenario of gear 4 at the current offset reaches 20.0 seconds while gear 5 already passed it
- **THEN** one notification is raised for gear 4

### Requirement: Discard the worst scenario
The analysis SHALL be able to discard the worst scenario of one given gear: the eligible scenario of that gear with the highest mean INJ_PULSE (ties go to the lower offset). It SHALL discard nothing when fewer than two scenarios of that gear are eligible, and nothing when the worst scenario is the one of the current offset (no other scenario is discarded in its place). Scenarios of other gears SHALL NOT be affected. Discarding SHALL take the scenario out of the active scenarios, so it no longer takes part in percentage differences or in choosing the best scenario, and the offset and the ignition map are unchanged. Returning to that gear and offset later SHALL start a new scenario from zero. The result SHALL tell whether a scenario was discarded.

#### Scenario: Worst discarded
- **WHEN** eligible scenarios of gear 5 at offsets `0`, `+1`, `+2` have mean injection time 1.12, 1.10 and 1.08 ms, the current offset is `+2` and gear 5 is discarded
- **THEN** the scenario at `0` is discarded and the other two remain

#### Scenario: Worst is the current one
- **WHEN** the scenario of the current offset has the highest mean injection time of the gear
- **THEN** nothing is discarded

#### Scenario: Fewer than two eligible
- **WHEN** only one scenario of the gear is eligible
- **THEN** nothing is discarded

#### Scenario: Not eligible scenarios are never the worst
- **WHEN** a scenario with little analysed time has the highest mean injection time
- **THEN** it is not discarded, and the worst eligible scenario is

#### Scenario: Tie
- **WHEN** offsets `0` and `+1` of the gear share the highest mean injection time
- **THEN** the scenario at `0` is discarded

#### Scenario: Other gear untouched
- **WHEN** gear 4 is discarded and gear 5 also has scenarios worse than their best
- **THEN** every scenario of gear 5 remains

#### Scenario: Returning to a discarded offset
- **WHEN** the scenario of gear 5 at `+1` was discarded and samples are later valid at `+1` in gear 5 again
- **THEN** a new scenario for gear 5 and `+1` exists with only the new samples

#### Scenario: Repeated
- **WHEN** the user discards repeatedly in one gear
- **THEN** scenarios of that gear are discarded one by one until fewer than two are eligible or the worst is the current one

## ADDED Requirements

### Requirement: Discarded scenarios are retained
The analysis SHALL retain every discarded scenario, with the statistics it had when it was discarded, until the next reset, and SHALL provide them separately from the active scenarios and flagged as discarded. Retained scenarios SHALL NOT take part in percentage differences, in choosing the best scenario, in the gears holding data or in later discards. Several retained scenarios MAY share a gear and offset, when a scenario was discarded and a new one was later created at the same gear and offset.

#### Scenario: Discarded scenario retained
- **WHEN** the scenario of gear 5 at `0` is discarded
- **THEN** it is absent from the active scenarios and present among the discarded ones with its mean injection time and analysed time

#### Scenario: Same key twice
- **WHEN** the scenario of gear 5 at `+1` is discarded and a new scenario at gear 5 and `+1` is later created and discarded
- **THEN** both are retained as discarded scenarios

#### Scenario: Discarded not compared
- **WHEN** a discarded scenario had the lowest mean MAP of its gear
- **THEN** the MAP percentage differences of the remaining scenarios are relative to the lowest mean among the active scenarios, and the discarded scenario is not the best scenario

#### Scenario: Cleared by reset
- **WHEN** the analysis is reset
- **THEN** there are no retained discarded scenarios
