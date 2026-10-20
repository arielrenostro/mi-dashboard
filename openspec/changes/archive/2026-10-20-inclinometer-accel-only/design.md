## Context

The production firmware (`inclinometer/inclinometro_6500.ino`) integrates the gyroscope and lets the accelerometer correct it only while the acceleration magnitude is within 0.15 g of 1 g. Captures from the real GY-521 showed 0.69 g at rest (Z reads +0.690 face up and -1.380 face down: gain about 1.035, offset about -0.345 g), so the gate never opens and the angle is open-loop. See proposal.md - Why. The experiment `inclinometer/experiments/accel_only/accel_only.ino` was run on the hardware and gave the expected behavior (stable, no drift, returns to level in about half a second with a 0.2 s filter), so this change brings it into the production firmware and removes what it made useless. The app side is `app/gyro/` (protocol, state, connection) and two screens.

## Goals / Non-Goals

**Goals:**
- Pitch and roll from the calibrated accelerometer only, without drift.
- A one-time, repeatable bench calibration that survives resets.
- Remove every gyroscope-only artifact from firmware, protocol, app and docs.

**Non-Goals:**
- Renaming the `gyro.*` setting, the `app/gyro` package, `GyroState` or the `Giroscópio` heading of the Settings screen (cosmetic, a later change).
- The PlatformIO migration and the firmware file name (`inclinometro_6500.ino` stays until then).
- Calibrating the accelerometer from the dashboard (it is done on the bench with a serial terminal).
- Compensating longitudinal acceleration: braking and accelerating still read as inclination, which is acceptable because the analysis then refuses to sample.

## Decisions

1. **Accelerometer only.** Gravity gives the angle directly at cruising speed, so there is nothing to drift. A gyroscope would only help in short transients and cannot separate a sustained small acceleration from a tilt either (0.05 g changes the magnitude by about 0.001 g). Alternative: fix the gate (relative 1 g reference), rejected because the angle would still depend on an uncalibrated accelerometer and the gyro adds code without adding a capability the use case needs.

2. **Seven-value `#D`.** The gyroscope columns have no meaning any more, so they are dropped rather than sent as zeros. The header and the app's parser change with them. Alternative: keep sending `gx/gy/gz` for diagnostics, rejected as dead data that the contract would have to keep promising. The Arduino-to-app contract stays one line shape per tag.

3. **Commands reduced to `#Z` plus the `#K` family.** `#C` has nothing to calibrate and `#R` was never sent by the app (a reset or a new `#Z` do the same job). The experiment's `#T` (live filter constant) is not carried over: the constant is 0.2 s in the firmware and changes by editing it, which a PlatformIO build makes cheap. An unknown or retired command gets `#M;COMANDO_DESCONHECIDO;`.

4. **Six-position calibration with `offset = (up + down) / 2`, `gain = (up - down) / 2`, stored in EEPROM.** The Arduino resets whenever the serial port opens, so a RAM-only calibration would vanish; the EEPROM keeps it. Each position averages 100 samples (about 0.5 s) so the stream pause stays under the app's 1 s no-signal limit (the experiment used 200 and paused for 1 s). The result is accepted only when every gain is within 0.5 to 1.5; otherwise the six captures are discarded. Alternatives: constants in the sketch (needs a rebuild per module and per recalibration) and a hardware offset register write (not portable across MPU-6050/6500 and clones).

5. **Direct register access instead of the MPU6500_WE library.** The registers used (power, config, accelerometer config, the 14-byte block from `0x3B`) are common to MPU-6050 and MPU-6500, the GY-521 board works, and the library's identity check and its offset handling are out of the picture. The chip identity is reported at boot as `#M;WHO_AM_I_<HEX>;` and never enforced. Alternative: keep the library, rejected because it hid whether the -0.345 g offset came from it and ties the project to one chip.

6. **Filter: first-order low-pass of the three acceleration values, 0.2 s, started at the first sample.** The 0.5 s of the first experiment was too slow to read 0 after leveling the board; 0.2 s reaches about 0 in half a second. Vibration is the cost and was not measured on the car, so the value is revisited in the manual verification task. Filtering the vector (not the angles) keeps the angle formulas exact.

7. **`#Z` averages 25 fresh samples (about 0.12 s) and restarts the filter in that pose.** Taking the zero from the filtered vector (as the experiment did first) captured a value the filter had not reached yet, so the reading moved after the zero. The restart makes pitch and roll exactly 0 at once.

8. **The app loses the `calibrating` state outright.** No timer, no pause tolerance, no row. An old firmware that still sends `#C;CALIBRANDO;` or the ten-value `#D` simply has those lines ignored (the ten-value line fails the length check and the device appears as no signal), which is the loud failure we want after a protocol change. The ignition tuning scenario `Calibrating` stays as a negative scenario (the box never reads `calibrando…`) only so the requirement keeps its name, because three other requirements cite it.

9. **Spec bookkeeping.** The validator forbids a modified requirement from losing scenarios, so requirements that lose scenarios are replaced (`REMOVED` plus `ADDED` under a new name: `Zero flag`, `Data stream presence`, `Zero acknowledgement`, `Zero command`, `Zero row`, `Accelerometer angle estimation`, `Command acknowledgements`, `Zero on command`). The Purpose lines of `gyro-connection`, `settings-screen` and `inclinometer-firmware` still mention recalibration or the gyroscope and are edited directly in the main specs when the change is synced (deltas cannot change a Purpose).

## Risks / Trade-offs

- [The bench calibration is manual and a bad position silently gives a bad calibration] → The gain range check rejects the grossly wrong cases, `#KP` shows the numbers, and the verification task checks that every face reads about 1 g.
- [A module with a very large offset (this one: -0.345 g) may drift further with temperature] → The temperature is in the data line; recalibrate if the zero walks. Replacing the module is the fallback.
- [The 0.2 s filter passes road and engine vibration to the pitch] → The ignition analysis already needs a settled window and a tolerance of a few degrees; tune the constant in the manual verification on the car.
- [Firmware and app out of sync after the protocol change] → Flash both together; a mismatch shows as `Sem sinal` or no zero, never as a wrong angle.
- [A module mounted rotated about the vertical axis mixes roll into pitch] → Mount it aligned with the car; the README says so.
- [Accelerating or braking reads as a slope] → Accepted; it makes the analysis refuse to sample, which is the desired behavior at cruise.

## Migration Plan

1. Land the app and test changes together with the firmware change in one commit.
2. Flash the new firmware, open a serial terminal, check `WHO_AM_I_`, run the six-position calibration, confirm each face reads about 1 g.
3. Connect the dashboard, zero on a level surface, check the Settings screen and the inclination box.
4. Rollback: revert the commit and reflash the previous firmware (the stored calibration is ignored by it).

## Open Questions

- The final value of the filter constant (0.2 s now) after a drive; a one-line change of the firmware and its spec.
