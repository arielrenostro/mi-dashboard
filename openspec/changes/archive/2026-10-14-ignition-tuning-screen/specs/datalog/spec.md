## MODIFIED Requirements

### Requirement: Manual event mark
On the Dashboard, the VE calibration screen and the Ignition tuning screen, pressing Enter or Return SHALL play `datalog.mark_sound` from the start (restarting it if it is playing) and request an event mark for the next logged row. Auto-repeat events SHALL be ignored, so holding the key marks once. The request is a flag, not a counter: several presses before the next frame produce a single `MARK` row. On the Home screen Enter SHALL keep opening the selected screen and SHALL NOT mark.

#### Scenario: Mark during a run
- **WHEN** the user presses Enter on the Dashboard and the next frame arrives
- **THEN** the sound plays and that row has `MARK` in the Event column

#### Scenario: Mark on the Ignition tuning screen
- **WHEN** the user presses Enter on the Ignition tuning screen and the next frame arrives
- **THEN** the sound plays and that row has `MARK` in the Event column

#### Scenario: Held key
- **WHEN** the user holds Enter
- **THEN** only one mark is requested

#### Scenario: Two presses before a frame
- **WHEN** the user presses Enter twice before the next frame
- **THEN** only the next row has `MARK`

#### Scenario: Home screen
- **WHEN** the user presses Enter on Home
- **THEN** the selected screen opens and no mark is requested
