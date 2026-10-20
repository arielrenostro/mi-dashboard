## Why

The inclinometer firmware estimates the angle with a gyroscope plus a gated complementary filter. On the real module (a GY-521) the gate never opens: the accelerometer reads 0.69 g at rest (a Z offset near -0.345 g), so the angle is pure gyro integration, never self-corrects, and drifts by tens of degrees after a movement. The dashboard only needs to know whether the nose is level while cruising, which the accelerometer alone gives without drift once its offset and gain are calibrated. The gyroscope, its calibration and the commands around it are dead weight. An experiment (`inclinometer/experiments/accel_only`) already confirmed the approach on the hardware.

## What Changes

- **BREAKING** The firmware computes pitch and roll only from the accelerometer: per-axis offset and gain correction, then a first-order low-pass filter (0.2 s), then `atan2`. No gyroscope integration and no 1 g gate.
- **BREAKING** The `#D` line drops the gyroscope columns: seven values, `t_ms;pitch;roll;ax_g;ay_g;az_g;temp_c`. The `#H` header follows.
- **BREAKING** The `#C` (gyroscope recalibration) and `#R` (remove zero) commands are removed, together with the replies `#C;CALIBRANDO;`, `#C;OK;`, `#R;OK;` and the app's `calibrating` state, its 10 s timer and its pause tolerance. A device that receives them answers `#M;COMANDO_DESCONHECIDO;`.
- New one-time bench calibration of the accelerometer in six positions with the commands `#K<axis><U|D>` (and `#KP` to print, `#KR` to reset), stored in the board's EEPROM, so the offset that locked the old filter is corrected.
- `#Z` takes the zero from a fresh ~0.12 s average and restarts the filter in that pose, so the displayed pitch and roll are 0 at once.
- The firmware reads the MPU registers directly (MPU-6050 and MPU-6500 compatible, GY-521 modules work) instead of the MPU6500_WE library, and reports the chip identity at boot as `#M;WHO_AM_I_<HEX>;`.
- The Settings screen loses the `Recalibrar giroscópio` row and its "stop the car" guard; the `Calibrando…` state disappears from the Settings readout and from the ignition tuning inclination box.
- The contract test, the READMEs and `CLAUDE.md` follow; the experiment folder is removed once the production firmware has its content.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `inclinometer-firmware`: accelerometer-only angle estimation with calibration and a low-pass filter; seven-value data line; commands reduced to `#Z` and the `#K` calibration family; boot with identity report; gyroscope calibration removed.
- `gyro-connection`: seven-value data line; only `#Z;OK` is a state-changing reply; `calibrating` state and calibration timer removed; only `#Z` is sent.
- `settings-screen`: `Recalibrar giroscópio` row removed (eight selectable rows); readout without `Calibrando…`.
- `ignition-tuning-screen`: the inclination box has no `calibrando…` state.

## Impact

- Code: `dashboard/app/gyro/protocol.py`, `state.py`, `connection.py`; `dashboard/app/ui/settings/screen.py`; `dashboard/app/ui/ignition_tuning/screen.py`.
- Firmware: `inclinometer/inclinometro_6500.ino` (rewritten from the experiment; the file name stays until the PlatformIO migration); `inclinometer/experiments/accel_only/` removed.
- Tests: `dashboard/tests/test_gyro_connection.py`, `test_settings_screen.py`, `test_ignition_tuning_screen.py`, `test_inclinometer_firmware_contract.py`.
- Docs: `inclinometer/README.md`, `dashboard/README.md`, `CLAUDE.md`; the Purpose lines of `gyro-connection`, `settings-screen` and `inclinometer-firmware`.
- Firmware and app must be updated together (the data line changes shape). The module needs the six-position calibration once after flashing; without it the old behavior (offset 0, gain 1) applies.
- Not unit-testable: the angle accuracy, the calibration on the real sensor and the low-pass feel on the car (manual verification task).
- Out of scope: renaming the `gyro.*` setting, the `app/gyro` package and the `Giroscópio` heading, and the PlatformIO migration.
