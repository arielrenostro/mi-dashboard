## MODIFIED Requirements

### Requirement: Screen layout
The screen SHALL consist of a top bar of live values and status on two lines, a central area with one column per scenario of the shown gear (see ignition-analysis and "Shown gear"), and a footer with the key hints `↑ +1°   ↓ -1°   ←→ Marcha   Espaço Pausa   X Descarta pior   R Resetar   ESC Voltar`. The background SHALL be black and zones SHALL be separated by thin dark lines. Text SHALL be large enough to be read at a glance.

#### Scenario: Footer hints
- **WHEN** the screen is shown
- **THEN** the footer lists the keys ↑, ↓, ←→, Space, X, R and ESC

### Requirement: Top bar
The first line of the top bar SHALL show the live display strings of RPM, MAP, PEDAL, GEAR, IGN and LAMBDA, the current offset (for example `+2°`, `0°`, `-1°`), and a status label. The second line SHALL show the live display strings of CLT and IAT, the gear indicator and the analysed RPM band. The gear indicator SHALL list every configured gear in ascending order as `<n>ª`, enclose the shown gear in brackets (`[5ª]`) and follow with `•` each gear that holds at least one active scenario, inside the brackets for the shown gear (for example `4ª•  [5ª•]`). The RPM band SHALL read `Faixa <rpm_min>-<rpm_max>` from the configuration. The status SHALL be exactly one of, in this priority: `PAUSADO` while the analysis is paused; `AGUARDANDO ECU` while the ignition map is not loaded; `ESTABILIZANDO` while samples are being discarded for settling (after a write, a resume or the lambda loop closing again); `FORA DA FAIXA` while RPM, gear or lambda loop do not satisfy the sample conditions; `ANALISANDO` otherwise. Values that were never received SHALL be shown as `--`.

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
On this screen: ↑ SHALL raise the offset by 1 degree; ↓ SHALL lower it by 1 degree; ← and → SHALL change the shown gear (see "Shown gear"); Space SHALL toggle pause and resume; X SHALL discard the worst scenario of the shown gear (see ignition-analysis), changing nothing when there is none to discard; R SHALL reset (offset to 0, original map restored, the scenarios of every gear cleared, analysis resumed); ESC SHALL return to Home. Auto-repeat events SHALL be ignored for every key, so holding a key acts once. ↑, ↓ and R SHALL schedule the ignition write. ↑ and ↓ SHALL do nothing while the ignition map is not loaded. No other key SHALL change the offset, the map or the analysis.

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

#### Scenario: Back to Home
- **WHEN** the user presses ESC
- **THEN** the Home screen is shown

## ADDED Requirements

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
