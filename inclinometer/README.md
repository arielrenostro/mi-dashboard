# Master Injection Dashboard: inclinometer (Arduino)

An optional inclinometer for the [dashboard](../README.md): an Arduino with an MPU-6500 (accelerometer + gyroscope) that tells the ignition tuning screen when the car is not level. A slope changes the load the engine needs, so samples taken uphill or downhill are not comparable with samples taken on the flat.

The firmware is [`inclinometro_6500.ino`](inclinometro_6500.ino), an Arduino IDE sketch. It needs the **MPU6500_WE** library (Wolfgang Ewald): Arduino IDE → Manage Libraries → "MPU6500_WE". This page describes what the sketch does and what the dashboard expects from it.

How the dashboard uses the device (setup, the manual zero, when the analysis samples, the inclination box) is in the [Dashboard README](../dashboard/README.md#inclinometer-optional). The behavior the app expects is specified in [`openspec/specs/gyro-connection/spec.md`](../openspec/specs/gyro-connection/spec.md).

```
+-----------+  serial 115200 8N1  +-----------------+   Bluetooth   +-----+
| Arduino   | <-----------------> | Dashboard (PC)  | <-----------> | ECU |
| MPU-6500  |   #D ... #Z, #C     | dashboard/      |   COM port    +-----+
+-----------+                     +-----------------+
```

## Hardware

- Arduino board (the sketch comments mention Nano / Uno) with an **MPU-6500** (the sensor gives acceleration, angular rate and temperature).
- Wiring: `VCC` to 5 V (module with regulator) or 3.3 V, `GND` to `GND`, `SDA` to `A4`, `SCL` to `A5`. I2C address `0x68` (`AD0` to `GND`, the one the sketch uses) or `0x69` (`AD0` to `VCC`, needs `MPU_ADDR` changed in the sketch).
- Serial link to the PC, opened by the dashboard on the port set in `gyro.port` (for example `COM7`).
- Orientation assumed by the sketch: X = front of the car, Y = left, Z = up. Angle convention: **positive pitch = nose down**, positive roll = right side down.

## Serial link

**115200 baud, 8 data bits, no parity, 1 stop bit.** The baud rate is fixed on the app side. The device sends **100 data lines per second**.

Opening the port restarts many Arduino boards. The dashboard expects that: after every connection it treats the device as not zeroed until you zero it again.

## Protocol

Every line ends with `\n` (a trailing `\r` is ignored), is split at `;`, and ends with a `;` (so the last item is empty). The first item decides the meaning. The angles are **already filtered and zeroed by the device**; the app stores no angle, and only the pitch takes part in the decision.

| Line | Direction | Meaning |
|------|-----------|---------|
| `#D;t_ms;pitch;roll;ax_g;ay_g;az_g;gx_dps;gy_dps;gz_dps;temp_c;` | device → app | data, 100 per second |
| `#H;…;` | device → app | header, sent once after the device starts (it restarted: the zero is lost) |
| `#M;<text>;` | device → app | message (see below), shown on the app's Settings screen |
| `#Z` | app → device | set the zero at the current position |
| `#C` | app → device | recalibrate the gyroscope (the app only sends it with the car stopped) |
| `#R` | (not sent by the app) | the device removes the zero and answers `#M;Zero removido;` |

Commands are the text followed by `\n`; the device upper-cases what it receives and answers `#M;Comando desconhecido;` to anything else. The app never sends `#R`.

### Data line (`#D`)

Exactly ten numeric values after `#D`, in this order:

| Field | Unit | Notes |
|-------|------|-------|
| `t_ms` | ms | device clock; going back means the device restarted |
| `pitch` | degrees | positive = nose down; the only angle the app uses |
| `roll` | degrees | positive = right side down; shown, never used to decide |
| `ax_g`, `ay_g`, `az_g` | g | acceleration |
| `gx_dps`, `gy_dps`, `gz_dps` | deg/s | angular rate |
| `temp_c` | °C | sensor temperature |

A data line with another number of values, or with a value that is not a number, is ignored by the app. Example: `#D;12840;1.37;-0.62;-0.024;-0.011;1.000;0.12;-0.05;0.03;31.4;`

### Messages (`#M`)

The app keeps the latest text for display, and these exact texts also change its state:

| Text | Meaning for the app |
|------|---------------------|
| `Zero definido` | the device is zeroed (the only thing that makes the app consider it zeroed) |
| `Zero removido` | the device is not zeroed |
| `Calibrando...` | the gyroscope is being calibrated; no data lines are needed for up to 10 seconds |
| `Calibracao ok` | the calibration ended; it does **not** make the device zeroed |

Any other text is only displayed. The texts have no accents, as the device sends them.

> **Known mismatch (firmware vs. spec):** the sketch sends `Calibrando giroscopio: mantenha o carro parado` where the app (spec `gyro-connection`, compared exactly) expects `Calibrando...`. Until one of them changes, after `#C` the app does not enter the `calibrating` state: the message is only displayed, and the ~1.5 s without data shows as "sem sinal" on the dashboard.

## Zero and calibration

- **The zero belongs to the device.** On `#Z` it takes the current position as level, answers `#M;Zero definido;` and keeps it. The app never sends `#Z` by itself.
- **The zero is lost** when the device restarts (`#H`, or `t_ms` going back), when the gyroscope is recalibrated, or when the port is opened again. In each of these the app stops using the inclination until you zero it again.
- **Recalibrating** (`#C`): answer `#M;Calibrando...;`, stop sending data for as long as it takes (the app waits up to 10 seconds), then `#M;Calibracao ok;`. The car must be stopped. The sketch averages 500 gyroscope samples (about 1.5 s) and keeps its stored zero; the app still asks you to zero again.
- **Filtering** (in the sketch): gyroscope ±500 °/s and accelerometer ±2 g with the sensor's low-pass filters (~41–44 Hz); a complementary filter (98 % gyroscope) that only lets the accelerometer correct the angle when the total acceleration is close to 1 g (not while braking, cornering or accelerating hard). The library's `autoOffsets()` is not used because it assumes a level module and would erase the dashboard's tilt.
- **No data for more than 1 second** (outside a calibration) makes the app show "sem sinal" and stop sampling, so the stream must be continuous.
