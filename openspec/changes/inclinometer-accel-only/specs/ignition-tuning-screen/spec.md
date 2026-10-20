## MODIFIED Requirements

### Requirement: Inclination box
The second line of the top bar SHALL have, right of CLT and IAT, a box with the vehicle inclination, refreshed with the rest of the screen. The box SHALL read `Inclinação: <value>`, where `<value>` is, by the inclinometer state: `desligada` (disabled), `desconectada` (disconnected), `sem sinal` (no signal), `sem zero (G)` (not zeroed), and, when usable, the pitch with sign and one decimal followed by `°` and an arrow (`+1.4° ↓` for a positive pitch, nose down; `-1.4° ↑` for a negative pitch, nose up; `0.0°` without arrow for a pitch that rounds to zero). While usable, the box SHALL be green when the absolute pitch is within `ignition_tuning.max_tilt_deg` and red when it is above. While `gyro.port` is set and the state is not usable the box SHALL be orange, and while the sensor is disabled it SHALL be gray. The box SHALL be shown in every state.

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
- **WHEN** an old firmware sends the retired calibration reply `#C;CALIBRANDO;`
- **THEN** the box never reads `calibrando…` and keeps showing the state it had

#### Scenario: Disabled
- **WHEN** `gyro.port` is empty
- **THEN** the box reads `Inclinação: desligada` in gray
