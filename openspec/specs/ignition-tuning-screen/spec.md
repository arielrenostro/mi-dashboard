# ignition-tuning-screen Specification

## Purpose

Defines the Ignition tuning screen used on the road to find the best spark advance for light-load cruising: the layout, the very small set of keys, the audible cues, the pause, and how the changed ignition map is written to the ECU.

## Requirements

### Requirement: Screen layout
The screen SHALL consist of a top bar of live values and status on two lines (the second line holds the inclination box, see "Inclination box"), a central area with one column per scenario of the shown gear (see ignition-analysis and "Shown gear"), and a footer with the key hints `↑ +1°   ↓ -1°   ←→ Marcha   Espaço Pausa   X Descarta pior   R Resetar   G Zerar inclinação   ESC Voltar`. The background SHALL be black and zones SHALL be separated by thin dark lines. Text SHALL be large enough to be read at a glance.

#### Scenario: Footer hints
- **WHEN** the screen is shown
- **THEN** the footer lists the keys ↑, ↓, ←→, Space, X, R, G and ESC

### Requirement: Top bar
The first line of the top bar SHALL show the live display strings of RPM, MAP, PEDAL, GEAR, IGN and LAMBDA, the current offset (for example `+2°`, `0°`, `-1°`), and a status label. The second line SHALL show the live display strings of CLT and IAT, the inclination box (see "Inclination box"), the gear indicator and the analysed RPM band, in that order from the left; both lines SHALL share the same column widths, so CLT and IAT are as wide as the cards of the first line. The gear indicator SHALL list every configured gear in ascending order as `<n>ª`, enclose the shown gear in brackets (`[5ª]`) and follow with `•` each gear that holds at least one active scenario, inside the brackets for the shown gear (for example `4ª•  [5ª•]`). The RPM band SHALL read `Faixa <rpm_min>-<rpm_max>` from the configuration. The status SHALL be exactly one of, in this priority: `PAUSADO` while the analysis is paused; `AGUARDANDO ECU` while the ignition map is not loaded; `AGUARDANDO SENSOR` while `gyro.port` is not empty and the inclination is not usable (see `gyro-connection`); `INCLINADO` while the inclination is usable and the absolute pitch is above `ignition_tuning.max_tilt_deg`; `ESTABILIZANDO` while samples are being discarded for settling (after a write, a resume, the lambda loop closing again or the inclination becoming usable and level); `FORA DA FAIXA` while RPM, gear or lambda loop do not satisfy the sample conditions; `ANALISANDO` otherwise. Values that were never received SHALL be shown as `--`.

#### Scenario: Analysing
- **WHEN** RPM is 3000, gear 5, lambda loop 2, the offset has settled and the analysis is running
- **THEN** the status reads `ANALISANDO`

#### Scenario: Out of range
- **WHEN** RPM is 3400
- **THEN** the status reads `FORA DA FAIXA`

#### Scenario: Paused has priority
- **WHEN** the analysis is paused and RPM is 3400
- **THEN** the status reads `PAUSADO`

#### Scenario: Map not loaded
- **WHEN** the ignition map has not been fully received
- **THEN** the status reads `AGUARDANDO ECU`

#### Scenario: Settling after the loop closes
- **WHEN** the lambda loop has just gone from `0` to `1` with RPM and gear in range
- **THEN** the status reads `ESTABILIZANDO` for the settle time and then `ANALISANDO`

#### Scenario: Waiting for the sensor
- **WHEN** `gyro.port` is `COM7`, the device is connected but not zeroed and the map is loaded
- **THEN** the status reads `AGUARDANDO SENSOR`

#### Scenario: Sensor has priority over the band
- **WHEN** `gyro.port` is `COM7`, the port cannot be opened and RPM is 3400
- **THEN** the status reads `AGUARDANDO SENSOR`

#### Scenario: Tilted
- **WHEN** the inclination is usable, the pitch is 4.5 and `max_tilt_deg` is 3
- **THEN** the status reads `INCLINADO`

#### Scenario: Settling after the inclination is level
- **WHEN** the pitch comes back from 4.5 to 1.0 with every other condition holding
- **THEN** the status reads `ESTABILIZANDO` for the settle time and then `ANALISANDO`

#### Scenario: No sensor configured
- **WHEN** `gyro.port` is empty
- **THEN** the status never reads `AGUARDANDO SENSOR` nor `INCLINADO`

#### Scenario: Coolant and intake temperature
- **WHEN** CLT is 87 and IAT is 41
- **THEN** the second line shows `87` and `41`

#### Scenario: Temperatures never received
- **WHEN** no CLT or IAT value has been received
- **THEN** the second line shows `--` for both

#### Scenario: Analysed RPM band
- **WHEN** `ignition_tuning.rpm_min` is 2900 and `ignition_tuning.rpm_max` is 3100
- **THEN** the second line shows `Faixa 2900-3100`

#### Scenario: Gear indicator
- **WHEN** the gears are `[4, 5]`, gear 5 is shown and only gear 4 holds active scenarios
- **THEN** the gear indicator reads `4ª•  [5ª]`

#### Scenario: Shown gear with data
- **WHEN** the gears are `[4, 5]`, gear 5 is shown and both gears hold active scenarios
- **THEN** the gear indicator reads `4ª•  [5ª•]`

#### Scenario: Single configured gear
- **WHEN** the gears are `[5]` and gear 5 holds no scenario
- **THEN** the gear indicator reads `[5ª]`

### Requirement: Scenario columns
For each active scenario of the shown gear, in ascending offset order from left to right, the screen SHALL show one column with, from top to bottom: the offset (`+1°`, `0° orig` for zero, `-1°`); the analysed time as `mm:ss`; the mean IGN; the mean injection time in ms with its percentage difference; the mean MAP with its percentage difference; the mean PEDAL with its percentage difference; the mean LAMBDA; and the knock count. The columns SHALL NOT repeat the analysed RPM band, which the top bar shows. A scenario that is not eligible SHALL show `--` instead of percentage differences. The column of the current offset SHALL be marked distinctly from the others. When the shown gear has no active scenario the central area SHALL show an empty-state message.

#### Scenario: Column content
- **WHEN** the scenario at `+1` of the shown gear has 38 seconds, mean injection time 1.08 ms, mean MAP 45.9 and mean PEDAL 21.0
- **THEN** its column shows `+1°`, `00:38`, `1.08`, `45.9` and `21.0` with their percentage differences, and no RPM band

#### Scenario: Ordering
- **WHEN** scenarios exist for `+1`, `-1` and `0` in the shown gear
- **THEN** the columns read `-1°`, `0° orig`, `+1°` from left to right

#### Scenario: Only the shown gear
- **WHEN** gear 4 has scenarios at `0` and `+1`, gear 5 has a scenario at `0` and gear 5 is shown
- **THEN** one column is shown

#### Scenario: Not eligible
- **WHEN** a scenario has less than the minimum analysed time
- **THEN** its percentage differences read `--`

#### Scenario: Empty
- **WHEN** no sample has been accepted yet
- **THEN** an empty-state message is shown in the central area

#### Scenario: Empty gear
- **WHEN** gear 4 has scenarios, gear 5 has none and gear 5 is shown
- **THEN** the empty-state message is shown

### Requirement: Percentage indicator and best highlight
Each percentage difference SHALL be shown with a sign and one decimal (for example `+2.2%`, `0.0%`), in green when it is 0 and in a warmer color the larger it is. The best scenario of the shown gear (see ignition-analysis) SHALL be highlighted with a border around its whole column, and no other column SHALL have that border.

#### Scenario: Best border
- **WHEN** the scenario at `+1` is the best scenario of the shown gear
- **THEN** its column has the highlight border and no other column has it

#### Scenario: No best
- **WHEN** fewer than two scenarios of the shown gear are eligible
- **THEN** no column has the highlight border

#### Scenario: Best of the other gear
- **WHEN** gear 4 has a best scenario, gear 5 has none and gear 5 is shown
- **THEN** no column has the highlight border

### Requirement: Keys
On this screen: ↑ SHALL raise the offset by 1 degree; ↓ SHALL lower it by 1 degree; ← and → SHALL change the shown gear (see "Shown gear"); Space SHALL toggle pause and resume; X SHALL discard the worst scenario of the shown gear (see ignition-analysis), changing nothing when there is none to discard; R SHALL reset (offset to 0, original map restored, the scenarios of every gear cleared, analysis resumed); G SHALL send the zero command to the inclinometer (see "Inclination box") and nothing else; ESC SHALL return to Home. Auto-repeat events SHALL be ignored for every key, so holding a key acts once. ↑, ↓ and R SHALL schedule the ignition write. ↑ and ↓ SHALL do nothing while the ignition map is not loaded. No other key SHALL change the offset, the map or the analysis.

#### Scenario: Raise
- **WHEN** the map is loaded and the user presses ↑
- **THEN** the offset becomes `+1`

#### Scenario: Held key
- **WHEN** the user holds ↑
- **THEN** the offset changes only once

#### Scenario: Map not loaded
- **WHEN** the ignition map is not loaded and the user presses ↑
- **THEN** the offset stays `0` and nothing is written

#### Scenario: Pause toggle
- **WHEN** the user presses Space twice
- **THEN** the analysis is paused and then running again

#### Scenario: Discard the worst
- **WHEN** three scenarios of the shown gear are eligible, the worst is not the current one, and the user presses X
- **THEN** the worst scenario's column disappears, the offset is unchanged and nothing is written to the ECU

#### Scenario: Discard only in the shown gear
- **WHEN** gear 5 is shown with three eligible scenarios, gear 4 also has a worse scenario, and the user presses X
- **THEN** the worst scenario of gear 5 is discarded and every scenario of gear 4 remains

#### Scenario: Worst is the current one
- **WHEN** the worst scenario of the shown gear is the one of the current offset and the user presses X
- **THEN** every column remains

#### Scenario: Nothing to compare
- **WHEN** fewer than two scenarios of the shown gear are eligible and the user presses X
- **THEN** every column remains

#### Scenario: Reset
- **WHEN** the offset is `+3` with scenarios in gears 4 and 5 and the user presses R
- **THEN** the offset is `0`, the scenarios of both gears are cleared, the analysis is running and a write of all 16 rows is scheduled

#### Scenario: Zero the inclination
- **WHEN** the inclinometer port is open and the user presses G
- **THEN** the zero command is sent and the offset, the scenarios, the pause state and the ECU are unchanged

#### Scenario: Zero without a sensor
- **WHEN** `gyro.port` is empty or the port is closed and the user presses G
- **THEN** nothing is sent and nothing else changes

#### Scenario: Back to Home
- **WHEN** the user presses ESC
- **THEN** the Home screen is shown

### Requirement: State kept while the screen is hidden
Leaving the screen with ESC SHALL NOT change the offset, the written map or the scenarios, and returning SHALL show them as they were. Telemetry received while the screen is hidden SHALL NOT be analysed.

#### Scenario: Leave and return
- **WHEN** the offset is `+2`, the user presses ESC and opens the screen again
- **THEN** the offset is still `+2` with the same scenarios

#### Scenario: Hidden
- **WHEN** valid telemetry arrives while Home is shown
- **THEN** no scenario changes

### Requirement: Live refresh
While the screen is active it SHALL refresh the top bar and the columns every 100 ms. The analysis SHALL consume every telemetry set received while the screen is active.

#### Scenario: Refresh stops when hidden
- **WHEN** the user presses ESC
- **THEN** the periodic refresh stops

### Requirement: Ignition write
Every offset change or reset SHALL (re)start a 1000 ms single-shot delay. Only when 1000 ms pass without another change SHALL pending rows be written. Pending rows SHALL be written in ascending order, each as the ECU ignition row command for that row (row index + 1) carrying all 16 current working values of the row. Each row SHALL be marked as sent before its command is queued. The write-on-memory command SHALL NOT be sent. When no row is pending, nothing SHALL be sent and no sound SHALL play. The moment the rows are queued is the moment settling starts (see ignition-analysis).

#### Scenario: Burst
- **WHEN** the user presses ↑ three times within one second each
- **THEN** a single write happens 1 second after the last press, with the offset `+3` values

#### Scenario: Rows written
- **WHEN** the offset is raised and rows 0 to 5 are pending
- **THEN** `#I01;…` to `#I06;…` are queued in that order, each with 16 values

#### Scenario: Not written
- **WHEN** the offset is raised and lowered back within the delay
- **THEN** no command is sent

#### Scenario: Reset writes everything
- **WHEN** the user presses R and 1 second passes
- **THEN** 16 row commands are queued with the original values

#### Scenario: No persistence
- **WHEN** rows are written
- **THEN** `#D04` is never sent

### Requirement: Audible cues
The driver is not expected to look at the screen, so the screen SHALL play: `ignition_tuning.write_sound` once (restarting it if playing) when a write has been queued; `ignition_tuning.ready_sound` when the scenario of the current offset reaches the minimum analysed time; `ignition_tuning.pause_sound` when the analysis is paused; and `ignition_tuning.resume_sound` when it is resumed; and `ignition_tuning.discard_sound` when a scenario was discarded (nothing plays when nothing was discarded). Sounds SHALL be played only while the screen is active.

#### Scenario: Write sound
- **WHEN** rows are queued
- **THEN** the write sound plays once

#### Scenario: Ready sound
- **WHEN** the current scenario reaches the minimum analysed time
- **THEN** the ready sound plays once

#### Scenario: Discard sound
- **WHEN** a scenario is discarded
- **THEN** the discard sound plays once

#### Scenario: Nothing discarded
- **WHEN** the user presses X and nothing is discarded
- **THEN** no sound plays

#### Scenario: Pause and resume sounds
- **WHEN** the user pauses and then resumes
- **THEN** the pause sound plays and then the resume sound plays

### Requirement: Shown gear
The screen SHALL show the scenarios of exactly one configured gear, the shown gear. Initially the shown gear SHALL be the highest configured gear. Each time the engaged gear (GEAR telemetry) changes to a configured gear, the shown gear SHALL become that gear; while the engaged gear is not a configured gear (neutral, another gear, never received) the shown gear SHALL stay as it is. ← SHALL show the next lower configured gear and → the next higher one, without wrapping and without changing the offset, the analysis or the ECU; with a single configured gear they do nothing. A manual choice SHALL last until the engaged gear changes to a configured gear. Changing the shown gear SHALL NOT change which gear is being sampled.

#### Scenario: Initial gear
- **WHEN** the gears are `[4, 5]` and the screen is created
- **THEN** gear 5 is shown

#### Scenario: Follows the engaged gear
- **WHEN** gear 5 is shown and the engaged gear changes to 4
- **THEN** gear 4 is shown

#### Scenario: Not a configured gear
- **WHEN** gear 4 is shown and the engaged gear changes to 3 or to neutral
- **THEN** gear 4 stays shown

#### Scenario: Manual change
- **WHEN** gear 5 is shown and the user presses ←
- **THEN** gear 4 is shown, and the offset, the scenarios and the analysis are unchanged

#### Scenario: Manual choice kept
- **WHEN** the user switched to gear 4 by pressing ← and telemetry in gear 5 keeps arriving
- **THEN** gear 4 stays shown while the engaged gear stays 5

#### Scenario: End of the list
- **WHEN** gear 5 is the highest configured gear, is shown and the user presses →
- **THEN** gear 5 stays shown

#### Scenario: Single gear
- **WHEN** the gears are `[5]` and the user presses ← or →
- **THEN** gear 5 stays shown

#### Scenario: Sampling is independent of the display
- **WHEN** gear 4 is shown by a manual choice and valid samples arrive in gear 5
- **THEN** the scenarios of gear 5 accumulate and the columns of gear 4 do not change

### Requirement: Inclination box
The second line of the top bar SHALL have, right of CLT and IAT, a box with the vehicle inclination, refreshed with the rest of the screen. The box SHALL read `Inclinação: <value>`, where `<value>` is, by the inclinometer state: `desligada` (disabled), `desconectada` (disconnected), `calibrando…` (calibrating), `sem sinal` (no signal), `sem zero (G)` (not zeroed), and, when usable, the pitch with sign and one decimal followed by `°` and an arrow (`+1.4° ↓` for a positive pitch, nose down; `-1.4° ↑` for a negative pitch, nose up; `0.0°` without arrow for a pitch that rounds to zero). While usable, the box SHALL be green when the absolute pitch is within `ignition_tuning.max_tilt_deg` and red when it is above. While `gyro.port` is set and the state is not usable the box SHALL be orange, and while the sensor is disabled it SHALL be gray. The box SHALL be shown in every state.

#### Scenario: Nose down
- **WHEN** the inclination is usable with pitch 1.37
- **THEN** the box reads `Inclinação: +1.4° ↓` in green

#### Scenario: Nose up
- **WHEN** the inclination is usable with pitch -2.04 and `max_tilt_deg` is 3
- **THEN** the box reads `Inclinação: -2.0° ↑` in green

#### Scenario: Flat
- **WHEN** the inclination is usable with pitch 0.02
- **THEN** the box reads `Inclinação: 0.0°`

#### Scenario: Above the limit
- **WHEN** the inclination is usable with pitch 4.5 and `max_tilt_deg` is 3
- **THEN** the box reads `Inclinação: +4.5° ↓` in red

#### Scenario: Not zeroed
- **WHEN** the device is connected but not zeroed
- **THEN** the box reads `Inclinação: sem zero (G)` in orange

#### Scenario: No signal
- **WHEN** the device stopped sending data
- **THEN** the box reads `Inclinação: sem sinal` in orange

#### Scenario: Disconnected
- **WHEN** `gyro.port` is set and the port is not open
- **THEN** the box reads `Inclinação: desconectada` in orange

#### Scenario: Calibrating
- **WHEN** the device is calibrating
- **THEN** the box reads `Inclinação: calibrando…` in orange

#### Scenario: Disabled
- **WHEN** `gyro.port` is empty
- **THEN** the box reads `Inclinação: desligada` in gray
