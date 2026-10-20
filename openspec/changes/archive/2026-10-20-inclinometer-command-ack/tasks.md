## 1. Protocol parser

- [x] 1.1 In `dashboard/app/gyro/protocol.py` add the reply type (command, status), the status constants `OK` and `CALIBRANDO`, parse `#Z`, `#R` and `#C` lines with exactly one status item (any other shape gives None), and remove the `MESSAGE_*` constants. Verify with new cases in `dashboard/tests/test_gyro_connection.py`: "Command reply", "Command reply with the wrong shape", "Not finite" (and the existing line-format scenarios still pass).

## 2. Gyro state

- [x] 2.1 In `dashboard/app/gyro/state.py` react to the replies: `#Z;OK` sets `zeroed`; `#R;OK` and `#C;CALIBRANDO` clear it; `#C;CALIBRANDO` starts the calibration clock; `#C;OK` ends it without setting `zeroed`; other statuses only display; every reply becomes the latest message as `<CMD>: <STATUS>`; `#M` texts never change a flag. Verify with tests in `dashboard/tests/test_gyro_connection.py` named after the scenarios "Zero acknowledged", "Calibration reply as message", "Unknown status", "Not case folded", "Old state texts do nothing", "Zeroed by the device", "Zero removed", "Calibrating", "Calibration ends", "Boot calibration", "Pause during calibration", "Calibration never ends", "Sending changes nothing".
- [x] 2.2 Update the existing gyro-connection and settings-screen tests that feed the old texts (`dashboard/tests/test_gyro_connection.py`, `dashboard/tests/test_settings_screen.py`) to the new replies, and add the settings scenarios "Command reply as message" and "Device text message". Verify with `python -m pytest tests/test_gyro_connection.py tests/test_settings_screen.py` from `dashboard/`.

## 3. Firmware

- [x] 3.1 In `inclinometer/inclinometro_6500.ino` send the replies `#Z;OK;`, `#R;OK;`, `#C;CALIBRANDO;` / `#C;OK;` (also on the boot calibration), turn every `#M` text into uppercase with `_` and no accents (`COMANDO_DESCONHECIDO`, `MPU_NAO_RESPONDEU_CONFIRA_LIGACAO_E_ENDERECO_0X68_0X69`, `ENVIE_Z_COM_O_CARRO_EM_SOLO_PLANO_PARA_ZERAR`), drop the retired state texts, and update the header comment. Verify by reading the file against `specs/inclinometer-firmware/spec.md` ("Command replies", "Messages", "Boot sequence") and with task 4.1.
- [x] 3.2 Cannot be unit tested (real hardware): with the sketch flashed, open a serial terminal at 115200 and verify: boot prints `#C;CALIBRANDO;`, `#C;OK;`, the hint `#M`, `#H` and then 100 `#D` lines per second; `#Z` answers `#Z;OK;` and the pitch goes near 0; `#R` answers `#R;OK;`; `#C` answers `#C;CALIBRANDO;`, stops the data, then `#C;OK;`; `#X` answers `#M;COMANDO_DESCONHECIDO;`; a lowercase `#z` works; tilting the board nose down gives a positive pitch and right side down a positive roll. Then connect the dashboard and confirm the Settings screen shows `Conectado, zerado` after `Zerar inclinação`, `Calibrando…` during `Recalibrar giroscópio` and `Conectado, sem zero` after it.

## 4. Contract test

- [x] 4.1 Create `dashboard/tests/test_inclinometer_firmware_contract.py`: one constant for the firmware source path (today the `.ino`), and tests named after "Contract check" that assert the source contains the full reply literals the app reacts to, the `#H` header built from the app's field names, the commands the app sends, and none of the retired texts (`Zero definido`, `Zero removido`, `Calibrando`, `Calibracao ok`). Verify it fails against the current firmware before task 3.1 and passes after.

## 5. Docs

- [x] 5.1 Update `inclinometer/README.md` (protocol table, `#M` section, zero and calibration section; remove the "Known mismatch" note) and the device-message examples in `dashboard/README.md`. Verify with `grep -rn "Zero definido\|Zero removido\|Calibracao ok\|Calibrando\.\.\." inclinometer dashboard/README.md dashboard/app dashboard/tests` returning nothing except `dashboard/tests/test_inclinometer_firmware_contract.py`, which names the retired texts on purpose to assert their absence.

## 6. Finish

- [x] 6.1 Run the full suite (`python -m pytest`, from `dashboard/`) and verify it passes; run `openspec validate inclinometer-command-ack` and verify it is valid.
