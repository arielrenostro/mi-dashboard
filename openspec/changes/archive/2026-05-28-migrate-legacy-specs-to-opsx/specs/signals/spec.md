## ADDED Requirements

### Requirement: Direct signals are read from ECU frame columns
The system SHALL read direct signals from absolute column positions in the combined `#D01;...;#D02;...` frame. Each signal MUST define: enum name, frame index, unit, raw-to-value converter, display format string, graph min/max, graph color, and alarm config (enabled, min, max, duration_s).

Signal table (enum name → index, converter, unit, alarm):
- `RPM` → 1, `int(raw)`, RPM, alarm: 0–6600
- `MAP` → 2, `int(raw)`, kPa, alarm: 0–165
- `BOOST` → 3, `int(raw)`, kPa, alarm disabled
- `LAMBDA` → 6, `float(raw)/1000`, λ, alarm disabled
- `INJ_UTIL` → 8, `int(raw)`, %, alarm: −999–90
- `VE` → 9, `float(raw)/10`, %, alarm disabled
- `IGN` → 10, `int(raw)`, º, alarm disabled
- `CLT` → 19, `int(raw)−273`, ºC, alarm: 0–95
- `IAT` → 20, `int(raw)−273`, ºC, alarm disabled
- `VSS` → 23, `int(raw)`, km/h, alarm: 0–150
- `LAMBDA_LOOP` → 24, `int(raw)`, —, alarm disabled
- `LAMBDA_TARGET` → 25, `float(raw)/1000`, λ, alarm disabled
- `FUEL_TRIM` → 26, `(float(raw)−1000)/10`, %, alarm: −20–20
- `BOOST_TARGET` → 28, `int(raw)`, kPa, alarm disabled
- `PEDAL` → 29, `min(100.0, (float(raw)/990.0)*100.0)`, %, alarm disabled
- `GEAR` → 33, `int(raw)`, —, alarm disabled

Converter notes:
- `CLT` / `IAT`: raw is Kelvin; subtract 273 to get Celsius.
- `LAMBDA` / `LAMBDA_TARGET`: raw is lambda × 1000; divide by 1000.
- `FUEL_TRIM`: raw offset 1000, scale ×10; formula `(raw − 1000) / 10`.
- `PEDAL`: raw range 0–990; clamp to 100.0 maximum.

#### Scenario: Signal value is parsed from frame
- **WHEN** a combined frame arrives with a raw value at a known index
- **THEN** the system applies the converter and stores the result as the signal's current value

#### Scenario: LAMBDA value is scaled correctly
- **WHEN** the raw frame value at index 6 is `980`
- **THEN** the parsed LAMBDA value SHALL be `0.980`

#### Scenario: CLT is converted from Kelvin
- **WHEN** the raw frame value at index 19 is `363`
- **THEN** the parsed CLT value SHALL be `90` ºC

### Requirement: Calculated signals are derived from already-parsed direct signals
The system SHALL support calculated signals that have no frame index and derive their value via a lambda over already-parsed data. Calculated signals MUST be defined after all their dependencies in the enum, because `SignalProcessor` iterates enum members in order.

#### Scenario: POWER is computed from MAP, VE, RPM, IAT, LAMBDA
- **WHEN** a frame is fully parsed
- **THEN** POWER SHALL be computed as:
  `air_mass = (MAP * VE * 10 * 0.001587 * RPM) / (287 * (IAT + 273) * 2 * 60)`
  `power_kw = air_mass / (9 * LAMBDA)`
  `power_hp = (power_kw * 3600 * 2.20462) / 0.8`

#### Scenario: TORQUE is computed after POWER
- **WHEN** POWER has been computed for the current frame
- **THEN** TORQUE SHALL be `(POWER * 716.2) / max(RPM, 1)` in Kgf.m

### Requirement: Alarm condition is declared per signal
Each signal with `alarm_enabled = true` MUST define `alarm_min` and `alarm_max`. An alarm condition SHALL exist when the signal value is outside `[alarm_min, alarm_max]`. Alarm default duration is 2.0 s per event window.

#### Scenario: Alarm is active when value exceeds max
- **WHEN** `INJ_UTIL` value is `95` and `alarm_max` is `90`
- **THEN** the alarm condition SHALL be active for that signal

#### Scenario: No alarm fires for alarm-disabled signal
- **WHEN** `BOOST` value is outside any range
- **THEN** no alarm SHALL fire because `alarm_enabled = false`
