## MODIFIED Requirements

### Requirement: Direct signal catalog
The system SHALL define these direct signals. Alarm columns give whether the alarm is enabled and its lower and upper limits (a value strictly below the lower limit or strictly above the upper limit is out of range; `-` means no limit).

| Signal | Name | Pos | Unit | Conversion | Display | Graph range | Color | Alarm enabled | Alarm min | Alarm max |
|---|---|---|---|---|---|---|---|---|---|---|
| RPM | RPM | 1 | RPM | integer | `{v}` | 0..7000 | red | yes | 0 | 6600 |
| MAP | MAP | 2 | kPa | integer | `{v}` | 20..250 | fuchsia | yes | 0 | 165 |
| BOOST | Boost | 3 | kPa | integer | `{v}` | 20..250 | blue | no | 0 | 165 |
| LAMBDA | λ | 6 | λ | raw/1000 | `{v:.2f}` | 0.5..1.5 | lime | no | 0.70 | 9999.0 |
| INJ_UTIL | Inj. Duty | 8 | % | integer | `{v}` | 0..100 | lime | yes | -999 | 90 |
| VE | VE | 9 | % | raw/10 | `{v:.1f}` | 0..1200 | lime | no | - | - |
| IGN | Ign | 10 | º | integer | `{v}` | -45..45 | lime | no | 0 | 40 |
| CLT | CLT | 19 | ºC | integer - 273 | `{v}` | -20..120 | orange | yes | 0 | 95 |
| IAT | IAT | 20 | ºC | integer - 273 | `{v}` | -20..120 | DodgerBlue | no | 0 | 80 |
| VSS | Speed | 23 | km/h | integer | `{v}` | 0..200 | blue | yes | 0 | 150 |
| LAMBDA_LOOP | λ Loop | 24 | - | integer | `Closed` if v = 1, `Closed+Corr` if v = 2, else `Open` | 0..2 | orange | no | - | - |
| LAMBDA_TARGET | λ Target | 25 | λ | raw/1000 | `{v:.2f}` | 0.5..1.5 | blue | no | 0.70 | 1.30 |
| FUEL_TRIM | Fuel Trim | 26 | % | (raw - 1000)/10 | `{v:.1f}` | -20..20 | gray | yes | -20 | 20 |
| BOOST_TARGET | Boost Target | 28 | kPa | integer | `{v}` | 20..250 | MediumSeaGreen | no | - | - |
| PEDAL | Pedal | 29 | % | min(100, raw/990*100) | `{v:.1f}` | 0..100 | MediumSeaGreen | no | - | - |
| GEAR | Gear | 33 | - | integer | `{v}` | 0..6 | lime | no | - | - |

#### Scenario: Temperature conversion
- **WHEN** field 19 is `342`
- **THEN** CLT is `69` and displayed as `69`

#### Scenario: Lambda conversion
- **WHEN** field 6 is `903`
- **THEN** LAMBDA is `0.903` and displayed as `0.90`

#### Scenario: Fuel trim conversion
- **WHEN** field 26 is `1001`
- **THEN** FUEL_TRIM is `0.1` and displayed as `0.1`

#### Scenario: Pedal clamp
- **WHEN** field 29 is `1200`
- **THEN** PEDAL is `100.0`

### Requirement: Lambda loop values
The LAMBDA_LOOP raw value SHALL mean: `0` open loop, `1` closed loop, `2` closed loop with automatic correction. The display string SHALL be `Closed` for value `1`, `Closed+Corr` for value `2`, and `Open` for every other value.

#### Scenario: Open loop
- **WHEN** field 24 is `0`
- **THEN** the display string is `Open`

#### Scenario: Closed loop
- **WHEN** field 24 is `1`
- **THEN** the display string is `Closed`

#### Scenario: Closed loop with automatic correction
- **WHEN** field 24 is `2`
- **THEN** the display string is `Closed+Corr`
