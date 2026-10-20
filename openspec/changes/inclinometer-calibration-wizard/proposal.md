## Why

The inclinometer's accelerometer must be calibrated once per module (six board positions, commands `#K…`), and today that needs a serial terminal and the Arduino IDE, with the dashboard disconnected from the port. A module with a large zero-g offset (the GY-521 in use reads 0.69 g flat) is unusable without it. The Settings screen already connects and zeroes the device, so the calibration belongs there: a guided wizard that sends the commands, waits for the device's acknowledgements and reports the result, with no second program and no port juggling.

## What Changes

- The Settings screen gets three rows under `Giroscópio`: `Calibrar acelerômetro` (opens a wizard), `Ver calibração` (`#KP`) and `Restaurar calibração` (`#KR`, asks for a second Enter).
- The wizard walks the six positions (`#KZU`, `#KZD`, `#KXU`, `#KXD`, `#KYU`, `#KYD`), one instruction per step, Enter to capture, and ends on `Calibração salva` or `Calibração inválida` from the device's own messages. Esc cancels; a missing acknowledgement ends the step with a message after a timeout.
- A new readout line shows the calibration the device reported (`#K;OFFSET;…;SCALE;…;`), after the wizard, `Ver calibração` or `Restaurar calibração`.
- **BREAKING** (inside the app) The app no longer sends only `#Z`: it also sends the six capture commands, `#KP` and `#KR`. The test that proved "no command other than zero" is replaced by one that proves the exact set.
- The protocol parser reads the `#K<axis><sense>;OK;`, `#KP;OK;` and `#KR;OK;` acknowledgements and the `#K;OFFSET;…` report line, and the state tracks the calibration progress (which captures were acknowledged, the outcome `CALIBRACAO_SALVA` / `CALIBRACAO_INVALIDA…`, the latest report).
- A saved or restored calibration clears the `zeroed` flag: the device keeps its old pitch/roll zero, taken with the previous offsets, so the user must zero again.
- The Settings selectable rows go from 8 to 11. The ignition screen, the firmware and `config.json` do not change (no new setting).
- READMEs describe the calibration from the dashboard; the bench terminal procedure stays as the alternative.

Depends on `inclinometer-accel-only`: that change defines the requirements this one modifies (`Zero flag`, `Zero command`, `Settings screen layout`, `Inclinometer readout`, …) and the `#K` firmware commands, whose hardware check (its task 6.1) the wizard relies on. Apply and archive this change after that one is archived.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `gyro-connection`: the `#K` acknowledgements and the calibration report are valid lines; calibration progress and outcome are tracked; a saved or restored calibration clears `zeroed`; the app may send the capture commands, `#KP` and `#KR` in addition to `#Z`.
- `settings-screen`: three new rows (eleven selectable rows), the calibration wizard, the confirmation of the restore, and a calibration line in the readout.

## Impact

- Code: `dashboard/app/gyro/protocol.py` (commands, acknowledgements, report), `state.py` (calibration progress), `connection.py` (send methods); `dashboard/app/ui/settings/screen.py` and a new wizard module next to it (`dashboard/app/ui/settings/calibration.py`).
- Tests: `dashboard/tests/test_gyro_connection.py`, `test_settings_screen.py`, a new `test_calibration_wizard.py`, `test_inclinometer_firmware_contract.py` (the app's commands are the ones the firmware accepts), `test_window.py` (Settings navigation count).
- Docs: `dashboard/README.md`, `inclinometer/README.md`, `CLAUDE.md` (Settings line).
- Not unit-testable: the real calibration on the sensor and the timing of the device's replies (manual verification task).
- Out of scope: any firmware change (including making the device clear its own pitch/roll zero when the calibration changes), a speed guard on the wizard (it is a bench operation), renaming the `gyro.*` setting, the `app/gyro` package and the `Giroscópio` heading.
