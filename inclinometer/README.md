# Master Injection Dashboard: inclinometer (Arduino)

An optional inclinometer for the [dashboard](../README.md): an Arduino with an accelerometer module (the GY-521, with an MPU-6050 or MPU-6500) that tells the ignition tuning screen when the car is not level. A slope changes the load the engine needs, so samples taken uphill or downhill are not comparable with samples taken on the flat.

The firmware is [`inclinometro_6500.ino`](inclinometro_6500.ino), an Arduino IDE sketch with **no library** besides the ones that ship with the Arduino core (`Wire`, `EEPROM`). The angle comes from the accelerometer alone: the gyroscope is not used. This page describes what the sketch does and what the dashboard expects from it.

How the dashboard uses the device (setup, the manual zero, when the analysis samples, the inclination box) is in the [Dashboard README](../dashboard/README.md#inclinometer-optional). The behavior the app expects is specified in [`openspec/specs/gyro-connection/spec.md`](../openspec/specs/gyro-connection/spec.md), and the firmware in [`openspec/specs/inclinometer-firmware/spec.md`](../openspec/specs/inclinometer-firmware/spec.md).

```
+-----------+  serial 115200 8N1  +-----------------+   Bluetooth   +-----+
| Arduino   | <-----------------> | Dashboard (PC)  | <-----------> | ECU |
| GY-521    |   #D ... #Z         | dashboard/      |   COM port    +-----+
+-----------+                     +-----------------+
```

## Hardware

- Arduino board (the sketch comments mention Nano / Uno) with a **GY-521** or any MPU-6050 / MPU-6500 module. The sketch reads the registers the two chips share and only reports the chip identity at boot (`#M;WHO_AM_I_70;` for an MPU-6500, `#M;WHO_AM_I_68;` for an MPU-6050); it never refuses a chip because of it.
- Wiring: `VCC` to 5 V (module with regulator) or 3.3 V, `GND` to `GND`, `SDA` to `A4`, `SCL` to `A5`. I2C address `0x68` (`AD0` to `GND`, the one the sketch uses) or `0x69` (`AD0` to `VCC`, needs `MPU_ADDR` changed in the sketch).
- Serial link to the PC, opened by the dashboard on the port set in `gyro.port` (for example `COM7`).
- Orientation assumed by the sketch: X = front of the car, Y = left, Z = up. Angle convention: **positive pitch = nose down**, positive roll = right side down. **Mount the module aligned with the car**: a module turned about the vertical axis mixes some roll into the pitch, which shows on a road that slopes sideways.

## Serial link

**115200 baud, 8 data bits, no parity, 1 stop bit.** The baud rate is fixed on the app side. The device sends **100 data lines per second**.

Opening the port restarts many Arduino boards. The dashboard expects that: after every connection it treats the device as not zeroed until you zero it again.

## How the angle is computed

```
raw accelerometer --(offset, gain per axis)--> g --(low-pass, 0.2 s)--> pitch = atan2(-ax, sqrt(ay^2 + az^2))
                                                                        roll  = atan2(ay, az)
```

- There is no integration, so **the angle does not drift**: put the module back level and it reads 0 again in about half a second.
- The low-pass filter has a time constant of 0.2 s (`TAU_S` in the sketch). A smaller value answers faster and passes more engine and road vibration.
- Accelerating or braking reads as a slope (error of about `a/g` radians: 0.05 g is about 3°). That is acceptable here: the analysis then refuses to sample, which is what you want at a steady cruise.
- Without the [calibration](#accelerometer-calibration) the offset is 0 and the gain 1. A module can have a large zero-g offset (one GY-521 read 0.69 g flat instead of 1.00 g), so calibrate once after flashing.

## Protocol

Every line ends with `\n` (a trailing `\r` is ignored), is split at `;`, and ends with a `;` (so the last item is empty). The first item decides the meaning. The angles are **already filtered and zeroed by the device**; the app stores no angle, and only the pitch takes part in the decision.

Everything the device sends as text (replies and messages) is **UPPERCASE, without accents, with `_` instead of a space**. The app sends its commands in uppercase too (the device also accepts lowercase).

| Line | Direction | Meaning |
|------|-----------|---------|
| `#D;t_ms;pitch;roll;ax_g;ay_g;az_g;temp_c;` | device → app | data, 100 per second |
| `#H;…;` | device → app | header, sent once after the device starts (it restarted: the zero is lost) |
| `#Z;OK;` | device → app | reply (ACK) to the zero command |
| `#M;<TEXT>;` | device → app | information (see below), shown on the app's Settings screen |
| `#Z` | app → device | set the zero at the current position |
| `#K…` | terminal → device | accelerometer calibration (see [below](#accelerometer-calibration)); the app never sends it |

Commands are the text followed by `\n`; the device upper-cases what it receives and answers `#M;COMANDO_DESCONHECIDO;` to anything else, including the old `#C` (gyroscope recalibration) and `#R` (remove the zero), which no longer exist.

### Data line (`#D`)

Exactly seven numeric values after `#D`, in this order:

| Field | Unit | Notes |
|-------|------|-------|
| `t_ms` | ms | device clock; going back means the device restarted |
| `pitch` | degrees | positive = nose down; the only angle the app uses |
| `roll` | degrees | positive = right side down; shown, never used to decide |
| `ax_g`, `ay_g`, `az_g` | g | acceleration, already calibrated and filtered |
| `temp_c` | °C | sensor temperature |

A data line with another number of values (such as the old ten-value format), or with a value that is not a number (`nan`, `inf`), is ignored by the app, so an old firmware shows as "sem sinal". Example: `#D;12840;1.37;-0.62;-0.024;-0.011;1.000;31.4;`

### Command reply (the ACK)

The zero command is answered with a line of the shape `#<CMD>;<STATUS>;`, sent after the command took effect. The app changes its state only on this reply, compared exactly:

| Command | Reply | Meaning for the app |
|---------|-------|---------------------|
| `#Z` | `#Z;OK;` | the device is zeroed (the only thing that makes the app consider it zeroed) |

The Settings screen shows the latest reply as `<CMD>: <STATUS>` (for example `Mensagem: Z: OK`).

### Messages (`#M`)

Information only, never a state change; the app keeps the latest text for display. The device sends:

| Text | When |
|------|------|
| `WHO_AM_I_<HEX>` | once at boot: the chip identity (`70` MPU-6500, `68` MPU-6050) |
| `ENVIE_Z_COM_O_CARRO_EM_SOLO_PLANO_PARA_ZERAR` | once at boot |
| `COMANDO_DESCONHECIDO` | the line received is not `#Z` or a valid `#K` command |
| `MPU_NAO_RESPONDEU_CONFIRA_LIGACAO_E_ENDERECO_0X68_0X69` | the sensor did not answer at boot; the device then stops (no header, no data) until it is reset |
| `FALHA_DE_LEITURA_DO_SENSOR` | the sensor stopped answering while a command was capturing samples |
| `CALIBRACAO_SALVA` / `CALIBRACAO_INVALIDA_REPITA_AS_POSICOES` | end of the accelerometer calibration |

## Zero

- **The zero belongs to the device.** On `#Z` it averages about 0.12 s of fresh samples (the board must be still), restarts the filter at that pose, answers `#Z;OK;` and keeps the zero, so pitch and roll read 0 at once. The app never sends `#Z` by itself.
- **The zero is lost** when the device restarts (`#H`, or `t_ms` going back) or when the port is opened again. In each of these the app stops using the inclination until you zero it again.
- Zero with the car on level ground, once the module is mounted.
- **No data for more than 1 second** makes the app show "sem sinal" and stop sampling, so the stream must be continuous. The commands that capture samples pause it for less than a second.

## Accelerometer calibration

Do it once after flashing a module, on the bench, with a serial terminal at 115200 (the Arduino IDE serial monitor, set to "Newline"). It finds the offset and gain of each axis and stores them in the board's EEPROM, so they survive a reset.

Put the board on a flat surface, **still**, with the axis below pointing **up** (`U`) or **down** (`D`), and send the command. Each one averages about 0.5 s and answers `#K<axis><sense>;OK;`:

| Command | Axis pointing | Typical way to hold it |
|---------|---------------|------------------------|
| `#KZU` | Z up | flat on the table, components up |
| `#KZD` | Z down | upside down |
| `#KXU` / `#KXD` | X up / down | standing on the edge, X axis vertical |
| `#KYU` / `#KYD` | Y up / down | standing on the other edge |

After the sixth position the device computes `offset = (up + down) / 2` and `gain = (up - down) / 2` for each axis, stores them and sends `#M;CALIBRACAO_SALVA;` and `#K;OFFSET;ox;oy;oz;SCALE;sx;sy;sz;`. When a gain is outside 0.5 to 1.5 it discards the six captures and sends `#M;CALIBRACAO_INVALIDA_REPITA_AS_POSICOES;`. Other commands: `#KP` answers `#KP;OK;` and prints the calibration in use; `#KR` restores offset 0 and gain 1.

To check it, hold any axis up: it should read about `+1.000` in `ax_g`/`ay_g`/`az_g`, and `sqrt(ax² + ay² + az²)` should be about 1.00 in any position.
