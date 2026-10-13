## ADDED Requirements

### Requirement: Clean shutdown of the alarm
When the app exits, the alarm SHALL stop the sound, stop polling and finish its thread.

#### Scenario: Exit while an alarm is sounding
- **WHEN** the user closes the app while the alarm sound is playing
- **THEN** the sound stops and the alarm thread finishes

#### Scenario: Exit with no alarm
- **WHEN** the user closes the app while no alarm is firing
- **THEN** the alarm thread finishes within its bounded wait
