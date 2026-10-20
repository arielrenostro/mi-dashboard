## Why

The inclinometer answers commands with free-text `#M` messages (`Zero definido`, `Calibrando giroscopio: ...`) that the app has to match character by character, and the two sides already disagree on one of them (the firmware says `Calibrando giroscopio: mantenha o carro parado`, the app waits for `Calibrando...`). A command also has no uniform acknowledgement, so the app cannot tell "received" from "ignored". The firmware has no spec at all, so nothing guards the contract between the two projects.

## What Changes

- **BREAKING** The device answers every command with a line of the same shape, `#<CMD>;<STATUS>;`, that works as the ACK: `#Z;OK;`, `#R;OK;`, and for the slow `#C` a first `#C;CALIBRANDO;` followed by `#C;OK;` when it ends.
- **BREAKING** The `#M` texts `Zero definido`, `Zero removido`, `Calibrando...` and `Calibracao ok` disappear. The app derives the zero flag and the calibration state from the command replies instead. `#M` keeps only diagnostic text (boot hint, sensor failure, unknown command) and never changes the app state.
- Everything the device sends after a command or as a message is UPPERCASE, without accents, with `_` instead of a space (`#M;COMANDO_DESCONHECIDO;`). Commands the app sends are uppercase too.
- The app parses the new reply lines, reacts to them, and shows the latest reply on the Settings screen as `<CMD>: <STATUS>` (for example `Mensagem: Z: OK`), so the result of a command stays visible there.
- The firmware is specified for the first time as the new capability `inclinometer-firmware` (serial framing, boot, `#D`/`#H`/`#M` lines, angle estimation, commands, zero, calibration), and the firmware, the READMEs and the tests are updated to it.
- A contract test reads the firmware source and checks it against the app's protocol constants, so a divergence like the old `Calibrando...` one fails the suite.

## Capabilities

### New Capabilities
- `inclinometer-firmware`: the device side of the inclinometer: serial link and line framing, boot sequence, data/header/message lines, angle estimation and zero, command replies (ACK), gyroscope recalibration, sensor configuration.

### Modified Capabilities
- `gyro-connection`: line format gains the command reply lines; `#M` text no longer changes state; zero state and calibration state follow `#Z;OK`, `#R;OK`, `#C;CALIBRANDO`, `#C;OK`; signal presence tolerates the pause after `#C;CALIBRANDO`; commands are acknowledged by the device.
- `settings-screen`: the device message line shows the latest `#M` text or the latest command reply as `<CMD>: <STATUS>`.

## Impact

- Code: `dashboard/app/gyro/protocol.py` (reply type, constants), `dashboard/app/gyro/state.py` (reactions, latest message), `dashboard/app/ui/settings/screen.py` only if the message line needs more than the stored text (expected: no change).
- Firmware: `inclinometer/inclinometro_6500.ino` (replies, uppercase messages, boot calibration lines). A PlatformIO project is coming; the spec does not depend on the file layout and the contract test reads the source path from one constant.
- Docs: `inclinometer/README.md` (protocol tables, the known-mismatch note goes away), `dashboard/README.md` (device message examples).
- Tests: `dashboard/tests/test_gyro_connection.py`, `dashboard/tests/test_settings_screen.py`, new `dashboard/tests/test_inclinometer_firmware_contract.py`.
- Firmware and app must be updated together: an old firmware never confirms the zero to a new app, and the reverse. No compatibility layer is kept.
- Not unit-testable: the angle filter and the sign conventions on real hardware (manual verification task).
