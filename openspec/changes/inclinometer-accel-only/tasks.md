## 1. Protocol parser

- [x] 1.1 In `dashboard/app/gyro/protocol.py` drop `gx_dps`, `gy_dps` and `gz_dps` from `DATA_FIELDS` and from `GyroReading` (seven values: `t_ms`, `pitch`, `roll`, `ax_g`, `ay_g`, `az_g`, `temp_c`), reduce `COMMANDS` to `#Z`, and remove `COMMAND_CALIBRATE`, `COMMAND_REMOVE_ZERO` and `STATUS_CALIBRATING`. Verify with updated cases in `dashboard/tests/test_gyro_connection.py` for the scenarios "Data line", "Wrong number of values" (six values and the old ten-value line), "Retired replies" (`#C;OK;` and `#R;OK;` give None) and the unchanged line-format scenarios.

## 2. Gyro state and connection

- [x] 2.1 In `dashboard/app/gyro/state.py` remove `GyroStatus.CALIBRATING`, `CALIBRATION_SECONDS`, the calibrating clock and the `#R` / `#C` reactions; keep `#Z;OK` setting `zeroed`, the other statuses only displayed, and the `<CMD>: <STATUS>` latest message. Verify with tests named after "Zero flag" (all six scenarios), "Data stream presence" (including "Short pause"), "Zero acknowledgement" (three scenarios), "Usable pitch", "Device messages" in `dashboard/tests/test_gyro_connection.py`; delete the tests of the removed calibration scenarios.
- [x] 2.2 In `dashboard/app/gyro/connection.py` remove `recalibrate()` and the `COMMAND_CALIBRATE` import. Verify with the "Zero command" scenarios ("Zero", "Port closed", "Sending changes nothing") in `dashboard/tests/test_gyro_connection.py` and by grepping that `recalibrate` no longer appears in `dashboard/app`.

## 3. Screens

- [x] 3.1 In `dashboard/app/ui/settings/screen.py` remove the `Recalibrar giroscópio` row, its handler, `STATUS_STOP_THE_CAR` and the `Calibrando…` state label; the screen has eight selectable rows. Verify with `dashboard/tests/test_settings_screen.py`: "Initial content" (eight rows), "Zero sent", "Zero without a device", the readout scenarios; delete the three recalibration scenario tests and any `recalibrate` method on the test fakes.
- [x] 3.2 In `dashboard/app/ui/ignition_tuning/screen.py` remove the `calibrando…` mapping of the inclination box. Verify with `dashboard/tests/test_ignition_tuning_screen.py`: the box scenarios keep passing and the "Calibrating" scenario asserts the box never reads `calibrando…`.

## 4. Firmware

- [x] 4.1 Rewrite `inclinometer/inclinometro_6500.ino` from `inclinometer/experiments/accel_only/accel_only.ino` following `specs/inclinometer-firmware/spec.md`: direct register access, `WHO_AM_I_<HEX>` at boot, seven-value `#D` and `#H`, calibrated and low-pass filtered (0.2 s) accelerometer, no gyroscope use, commands `#Z`, `#K<axis><U|D>`, `#KP`, `#KR` with the acknowledgements of "Command acknowledgements", calibration captures of 100 samples, EEPROM storage, no `#C`, `#R` or `#T`; update the header comment. Verify it compiles for the `nanoatmega328new` board with PlatformIO in a scratch project (`pio run`) and with task 5.1.
- [x] 4.2 Remove `inclinometer/experiments/` (the experiment is now the production firmware). Verify the directory is gone and `git status` shows no other reference to it (`grep -rn "experiments/accel_only" .` returns nothing outside `openspec/changes/archive`).

## 5. Contract test

- [x] 5.1 Update `dashboard/tests/test_inclinometer_firmware_contract.py`: the data line has the seven fields of `DATA_FIELDS`, the header literal is built from them, the only reply literal the app reacts to is `#Z;OK;`, the commands the firmware recognises include `#Z` and the `#K` family, and the source contains none of `#C;`, `#R;`, `gx_dps` and the previously retired texts; keep the uppercase check of the `#M` texts. Verify it fails against the old firmware before task 4.1 and passes after.

## 6. Hardware verification (cannot be unit tested)

- [ ] 6.1 With the board flashed: open a serial terminal at 115200 and verify `#M;WHO_AM_I_xx;` appears at boot; run `#KXU`, `#KXD`, `#KYU`, `#KYD`, `#KZU`, `#KZD` and verify `CALIBRACAO_SALVA` and the report line; reset the board and verify `#KP` reports the same values; verify each face-up axis reads about +1.000 g and the magnitude is about 1.00 g in several tilted positions; send `#Z` level and verify pitch and roll are 0 at once; tilt on a known wedge and compare the pitch; move the board quickly and put it back and verify it returns to 0 within about 1 s with no drift after ten minutes; send `#C` and `#R` and verify `#M;COMANDO_DESCONHECIDO;`. Then connect the dashboard and verify the Settings screen shows `Conectado, sem zero`, then `Conectado, zerado` after `Zerar inclinação`, with no `Calibrando…` state and no recalibration row, and that the ignition tuning inclination box follows the pitch. Finally drive and check that the pitch is stable enough with the 0.2 s filter; if not, adjust the constant and its spec line.

## 7. Docs

- [x] 7.1 Update `inclinometer/README.md` (hardware: GY-521 / MPU-6050 or 6500, no library; protocol table with the seven-value `#D`, only `#Z` and the `#K` calibration commands, the calibration procedure, the filter, the mounting advice), `dashboard/README.md` (remove the recalibration row, the `calibrando…` state and the moving-car rule for `#C`; the waiting-for-sensor list) and `CLAUDE.md` (the settings screen line). Verify with `grep -rniE "recalibr|gyroscope|#C\b|calibrando|gx_dps" inclinometer/README.md dashboard/README.md CLAUDE.md` returning only deliberate mentions (the retired-command note).
- [x] 7.2 When the change is synced, edit the Purpose lines of `openspec/specs/gyro-connection/spec.md`, `settings-screen/spec.md` and `inclinometer-firmware/spec.md` so they no longer mention the gyroscope or recalibration. Verify by reading the three Purpose paragraphs.

## 8. Finish

- [x] 8.1 Run the full suite (`python -m pytest`, from `dashboard/`) and verify it passes; run `openspec validate inclinometer-accel-only --strict` and verify it is valid.
