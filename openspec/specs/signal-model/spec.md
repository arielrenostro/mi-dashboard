# signal-model Specification

## Purpose

Defines the catalog of ECU telemetry signals (position, conversion, display format, graph range, color, alarm limits), the signals computed from other signals, and how a raw frame is turned into parsed values.

## Requirements

### Requirement: Frame parsing
For every received line that starts with `#D01` and splits into at least 2 fields on `;`, the system SHALL build one set of parsed signals and publish it to all consumers. Lines that do not start with `#D01` SHALL be ignored. For each signal, in catalog order, a direct signal SHALL be read from its absolute field position and converted; a direct signal whose position lies beyond the frame, or whose conversion fails, SHALL be omitted from that set. Each parsed signal SHALL carry the raw text, the converted value, and the display string.

#### Scenario: Valid frame
- **WHEN** a complete combined frame arrives
- **THEN** one set containing every convertible signal is published

#### Scenario: Short frame
- **WHEN** a frame has fewer fields than a signal's position
- **THEN** that signal is missing from the set and the others are present

#### Scenario: Foreign line
- **WHEN** a line does not start with `#D01`
- **THEN** nothing is published

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
| LAMBDA_LOOP | λ Loop | 24 | - | integer | `Closed` if v = 1, `Closed+C` if v = 2, else `Open` | 0..2 | orange | no | - | - |
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
The LAMBDA_LOOP raw value SHALL mean: `0` open loop, `1` closed loop, `2` closed loop with automatic correction. The display string SHALL be `Closed` for value `1`, `Closed+C` for value `2`, and `Open` for every other value.

#### Scenario: Open loop
- **WHEN** field 24 is `0`
- **THEN** the display string is `Open`

#### Scenario: Closed loop
- **WHEN** field 24 is `1`
- **THEN** the display string is `Closed`

#### Scenario: Closed loop with automatic correction
- **WHEN** field 24 is `2`
- **THEN** the display string is `Closed+C`

### Requirement: Calculated signals
The system SHALL compute these signals from previously parsed signals, after all direct signals, in this order. If a computation cannot be performed (for example a required signal is missing or a division by zero occurs), the signal's raw value and value SHALL both be `-1`.

- **VE_LAMBDA** (name `VE λ`, no unit, graph 0..200, cyan, display `{v:.2f}`, alarm disabled): `(LAMBDA.raw + FUEL_TRIM.raw - LAMBDA_TARGET.raw) * VE.raw / 10000`, using the raw integer field values.
- **POWER** (name `Power`, unit `HP`, graph 0..270, lime, display `{v:.1f}`, alarm disabled):
  `air_mass = (MAP * VE * 10 * 0.001587 * RPM) / (287 * (IAT + 273) * 2 * 60)`;
  `power_kw = air_mass / (9 * LAMBDA)`;
  `power_hp = (power_kw * 3600 * 2.20462) / 0.8`, using converted values.
- **TORQUE** (name `Torque`, unit `Kgf.m`, graph 0..30, blue, display `{v:.1f}`, alarm disabled): `(POWER * 716.2) / max(RPM, 1)`.

#### Scenario: Torque guard
- **WHEN** RPM is `0` and POWER is `0`
- **THEN** TORQUE is `0.0` (division uses 1)

#### Scenario: Failed computation
- **WHEN** a required signal is missing from the frame
- **THEN** the dependent calculated signal has value `-1`
