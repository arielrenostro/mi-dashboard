## Purpose

Defines how the operator manually opens or closes the ECU lambda feedback loop from the VE calibration screen during tuning.

## ADDED Requirements

### Requirement: Open loop key
On the VE calibration screen only, pressing O SHALL queue the lambda-loop-open command to the ECU and play the configured `ve_calibration.open_sound`.

#### Scenario: Open
- **WHEN** the user presses O on the VE calibration screen
- **THEN** `#D06` is queued and the open sound plays

### Requirement: Close loop key
On the VE calibration screen only, pressing P SHALL queue the lambda-loop-close command to the ECU and play the configured `ve_calibration.closed_sound`.

#### Scenario: Close
- **WHEN** the user presses P on the VE calibration screen
- **THEN** `#D05` is queued and the closed sound plays

### Requirement: Scope of the keys
O and P SHALL have no effect on other screens. Auto-repeat events are not filtered, so holding the key repeats the command and sound.

#### Scenario: Other screen
- **WHEN** the user presses O on the Dashboard
- **THEN** nothing is sent

### Requirement: Loop state comes from the ECU
Pressing O or P SHALL NOT change any value shown by the app; the displayed loop state SHALL change only when the ECU reports it in telemetry.

#### Scenario: Command then telemetry
- **WHEN** the user presses P and the ECU later reports loop value `1`
- **THEN** the top bar changes to `Closed` only after that report
