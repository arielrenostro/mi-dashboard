# ignition-tuning-screen Specification

## Purpose

Defines the Ignition tuning screen used on the road to find the best spark advance for light-load cruising: the layout, the very small set of keys, the audible cues, the pause, and how the changed ignition map is written to the ECU.

## Requirements

### Requirement: Screen layout
The screen SHALL consist of a top bar of live values and status, a central area with one column per scenario (see ignition-analysis), and a footer with the key hints `↑ +1°   ↓ -1°   Espaço Pausa   X Descarta pior   R Resetar   ESC Voltar`. The background SHALL be black and zones SHALL be separated by thin dark lines. Text SHALL be large enough to be read at a glance.

#### Scenario: Footer hints
- **WHEN** the screen is shown
- **THEN** the footer lists the keys ↑, ↓, Space, X, R and ESC

### Requirement: Top bar
The top bar SHALL show the live display strings of RPM, MAP, PEDAL, GEAR, IGN and LAMBDA, the current offset (for example `+2°`, `0°`, `-1°`), and a status label. The status SHALL be exactly one of, in this priority: `PAUSADO` while the analysis is paused; `AGUARDANDO ECU` while the ignition map is not loaded; `ESTABILIZANDO` while samples are being discarded for settling (after a write, a resume or the lambda loop closing again); `FORA DA FAIXA` while RPM, gear or lambda loop do not satisfy the sample conditions; `ANALISANDO` otherwise. Values that were never received SHALL be shown as `--`.

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

### Requirement: Scenario columns
For each scenario, in ascending offset order from left to right, the screen SHALL show one column with, from top to bottom: the offset (`+1°`, `0° orig` for zero, `-1°`); the analysed RPM band (`<rpm_min>-<rpm_max>`); the analysed time as `mm:ss`; the mean IGN; the mean injection time in ms with its percentage difference; the mean MAP with its percentage difference; the mean PEDAL with its percentage difference; the mean LAMBDA; and the knock count. A scenario that is not eligible SHALL show `--` instead of percentage differences. The column of the current offset SHALL be marked distinctly from the others. When no scenario exists the central area SHALL show an empty-state message.

#### Scenario: Column content
- **WHEN** the scenario at `+1` has 38 seconds, mean injection time 1.08 ms, mean MAP 45.9 and mean PEDAL 21.0
- **THEN** its column shows `+1°`, `2900-3100`, `00:38`, `1.08`, `45.9` and `21.0` with their percentage differences

#### Scenario: Ordering
- **WHEN** scenarios exist for `+1`, `-1` and `0`
- **THEN** the columns read `-1°`, `0° orig`, `+1°` from left to right

#### Scenario: Not eligible
- **WHEN** a scenario has less than the minimum analysed time
- **THEN** its percentage differences read `--`

#### Scenario: Empty
- **WHEN** no sample has been accepted yet
- **THEN** an empty-state message is shown in the central area

### Requirement: Percentage indicator and best highlight
Each percentage difference SHALL be shown with a sign and one decimal (for example `+2.2%`, `0.0%`), in green when it is 0 and in a warmer color the larger it is. The best scenario (see ignition-analysis) SHALL be highlighted with a border around its whole column, and no other column SHALL have that border.

#### Scenario: Best border
- **WHEN** the scenario at `+1` is the best scenario
- **THEN** its column has the highlight border and no other column has it

#### Scenario: No best
- **WHEN** fewer than two scenarios are eligible
- **THEN** no column has the highlight border

### Requirement: Keys
On this screen: ↑ SHALL raise the offset by 1 degree; ↓ SHALL lower it by 1 degree; Space SHALL toggle pause and resume; X SHALL discard the worst scenario (see ignition-analysis), changing nothing when there is none to discard; R SHALL reset (offset to 0, original map restored, scenarios cleared, analysis resumed); ESC SHALL return to Home. Auto-repeat events SHALL be ignored for every key, so holding a key acts once. ↑, ↓ and R SHALL schedule the ignition write. ↑ and ↓ SHALL do nothing while the ignition map is not loaded. No other key SHALL change the offset, the map or the analysis.

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
- **WHEN** three scenarios are eligible, the worst is not the current one, and the user presses X
- **THEN** the worst scenario's column disappears, the offset is unchanged and nothing is written to the ECU

#### Scenario: Worst is the current one
- **WHEN** the worst scenario is the one of the current offset and the user presses X
- **THEN** every column remains

#### Scenario: Nothing to compare
- **WHEN** fewer than two scenarios are eligible and the user presses X
- **THEN** every column remains

#### Scenario: Reset
- **WHEN** the offset is `+3` with scenarios and the user presses R
- **THEN** the offset is `0`, the scenarios are cleared, the analysis is running and a write of all 16 rows is scheduled

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
