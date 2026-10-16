## MODIFIED Requirements

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

## ADDED Requirements

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
