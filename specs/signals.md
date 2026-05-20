# Spec: ECU Signals

All telemetry signals read from the ECU. This is the single source of truth for signal definitions.

Implementation: `app/master/signal.py` (`Signal` enum).

---

## Direct signals

Signals read directly from a column in the ECU frame. The `index` is the absolute position in the combined `#D01;...;#D02;...` frame.

| Signal | Enum name | Index | Unit | Converter (raw → value) | Display format | Graph min | Graph max | Color | Alarm enabled | Alarm min | Alarm max |
|---|---|---|---|---|---|---|---|---|---|---|---|
| RPM | `RPM` | 1 | RPM | `int(raw)` | `"{value}"` | 0 | 7000 | red | yes | 0 | 6600 |
| MAP | `MAP` | 2 | kPa | `int(raw)` | `"{value}"` | 20 | 250 | fuchsia | yes | 0 | 165 |
| Boost | `BOOST` | 3 | kPa | `int(raw)` | `"{value}"` | 20 | 250 | blue | no | 0 | 165 |
| Lambda | `LAMBDA` | 6 | λ | `float(raw) / 1000` | `"{value:.2f}"` | 0.5 | 1.5 | lime | no | 0.70 | 9999.0 |
| Inj. Duty | `INJ_UTIL` | 8 | % | `int(raw)` | `"{value}"` | 0 | 100 | lime | yes | -999 | 90 |
| VE | `VE` | 9 | % | `float(raw) / 10` | `"{value:.1f}"` | 0 | 1200 | lime | no | — | — |
| Ignition Advance | `IGN` | 10 | º | `int(raw)` | `"{value}"` | -45 | 45 | lime | no | 0 | 40 |
| Coolant Temp | `CLT` | 19 | ºC | `int(raw) - 273` | `"{value}"` | -20 | 120 | orange | yes | 0 | 95 |
| Intake Air Temp | `IAT` | 20 | ºC | `int(raw) - 273` | `"{value}"` | -20 | 120 | DodgerBlue | no | 0 | 80 |
| Speed | `VSS` | 23 | km/h | `int(raw)` | `"{value}"` | 0 | 200 | blue | yes | 0 | 150 |
| Lambda Loop | `LAMBDA_LOOP` | 24 | — | `int(raw)` | `"Closed"` if value==1 else `"Open"` | 0 | 2 | orange | no | — | — |
| Lambda Target | `LAMBDA_TARGET` | 25 | λ | `float(raw) / 1000` | `"{value:.2f}"` | 0.5 | 1.5 | blue | no | 0.70 | 1.30 |
| Fuel Trim | `FUEL_TRIM` | 26 | % | `(float(raw) - 1000) / 10` | `"{value:.1f}"` | -20 | 20 | gray | yes | -20 | 20 |
| Boost Target | `BOOST_TARGET` | 28 | kPa | `int(raw)` | `"{value}"` | 20 | 250 | MediumSeaGreen | no | — | — |
| Pedal | `PEDAL` | 29 | % | `min(100.0, (float(raw) / 990.0) * 100.0)` | `"{value:.1f}"` | 0 | 100 | MediumSeaGreen | no | — | — |
| Gear | `GEAR` | 33 | — | `int(raw)` | `"{value}"` | 0 | 6 | lime | no | — | — |

### Notes on converters

- **CLT / IAT**: raw value is in Kelvin; subtract 273 to get Celsius.
- **LAMBDA / LAMBDA_TARGET**: raw value is lambda × 1000 (integer); divide by 1000.
- **FUEL_TRIM**: raw value is offset by 1000 and scaled ×10; formula: `(raw - 1000) / 10`.
- **PEDAL**: raw range is 0–990; clamped to 100% maximum.

---

## Calculated signals

Signals derived from already-parsed direct signals. They have no frame index.

**Intent:** calculated signals must be defined **after** all their dependencies in the enum, because `SignalProcessor` iterates the enum in order and passes the already-built `parsed_data` dict to the `value` lambda.

### POWER

```
name:  Power
unit:  HP
color: lime
graph: min=0, max=270
alarm: disabled

formula:
  air_mass   = (MAP * VE * 10 * 0.001587 * RPM) / (287 * (IAT + 273) * 2 * 60)
  power_kw   = air_mass / (9 * LAMBDA)
  power_hp   = (power_kw * 3600 * 2.20462) / 0.8

display: "{value:.1f}"
```

Dependencies: `MAP`, `VE`, `RPM`, `IAT`, `LAMBDA`

### TORQUE

```
name:  Torque
unit:  Kgf.m
color: blue
graph: min=0, max=30
alarm: disabled

formula:
  torque = (POWER * 716.2) / max(RPM, 1)

display: "{value:.1f}"
```

Dependencies: `POWER`, `RPM`

---

## Alarm behavior per signal

When a signal's value is outside `[alarm_min, alarm_max]` AND `alarm_enabled = yes`:

1. `AlarmProcessor` calls `vehicle_state.set_alarm(signal, True)`
2. The alarm is considered **firing** for 2 seconds from the last `set_alarm` call
3. `AlarmProcessor` emits the signal to `Dashboard.fire_field_alarm()` once (on the leading edge)
4. Visual: the grid cell flashes red/yellow at 200 ms intervals while firing
5. Audio: `alarm.wav` plays in a loop while any alarm is firing

See `alarm_system.md` for full alarm behavior spec.
