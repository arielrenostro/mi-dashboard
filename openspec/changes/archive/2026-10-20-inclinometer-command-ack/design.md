## Context

The app parses the inclinometer's lines in `app/gyro/protocol.py` and keeps the state in `app/gyro/state.py`; the firmware (`inclinometer/inclinometro_6500.ino`) answers commands with `#M` texts that the app compares exactly (`MESSAGE_*`). See proposal.md - Why for the problem. The firmware had no spec, and the repo is about to get a PlatformIO project, so the firmware's file name and layout will change soon.

## Goals / Non-Goals

**Goals:**
- One reply shape for every command, usable as an ACK, with the slow `#C` reporting both its start and its end.
- No state derived from free text: the app reacts to `#<CMD>;<STATUS>` only.
- A contract test between the firmware source and the app's protocol constants.

**Non-Goals:**
- A timeout or retry for commands without a reply (the spec only says sending changes nothing).
- A protocol version or backward compatibility with the old texts.
- The PlatformIO migration (next request); only the contract test's source path is kept in one place for it.
- Changing the zero semantics: the firmware keeps its zero through `#C` and the app still treats it as lost.

## Decisions

1. **Reply shape `#<CMD>;<STATUS>;`, statuses `OK` and `CALIBRANDO`.** The tag is the command received, so the parser needs one branch for all commands and a future command with a status like `ERRO` fits without a new format. Alternative: echo the command with no status (`#Z;`), rejected because `#C` needs a status anyway and two shapes would double the parser.

2. **`#M` only for information.** The unknown command is answered with `#M;COMANDO_DESCONHECIDO;` (there is no valid `<CMD>` to echo), and the boot hint and the sensor failure stay `#M`. Alternative: `#?;ERRO` for unknown commands, rejected as a tag the app would have to learn for something that never happens in normal use.

3. **Boot calibration uses the same two lines (`#C;CALIBRANDO;` / `#C;OK;`).** They describe the calibration, not only the answer to a command, so the app enters and leaves `calibrating` at boot too, as it did when the texts matched. The `#H` that follows clears the zero as before. Alternative: silent boot calibration, rejected because the ~2 s without data would show as `no signal` right after connecting.

4. **Lenient input, strict output.** The firmware keeps converting received letters to uppercase (so `#z` works from a terminal) while everything it sends is uppercase. The app only sends uppercase.

5. **The app shows replies as the latest message `<CMD>: <STATUS>`.** The Settings screen reads `snapshot.message`, which today is the `#M` text. Storing the reply there in the form `Z: OK` keeps the screen unchanged and keeps the requirement that the result of a command is visible. Alternative: a second field for the last reply, rejected because it would add a line to the screen for no new information.

6. **Replies change state by exact match; other statuses only display.** `#Z;ok;` or `#Z;ERRO;` leave the flag false, so a garbled line can never mark the device as zeroed. The zero flag, as before, is set by the device's reply and never by the act of sending.

7. **Contract test reads the firmware source as text.** `tests/test_inclinometer_firmware_contract.py` takes the path from one constant (today `inclinometer/inclinometro_6500.ino`; it becomes `src/main.cpp` or similar with PlatformIO) and checks: each command string the app sends, each reply line the app reacts to, the `#H` header equal to the app's field names, and that none of the retired `#M` state texts remain. It does not compile or run the firmware.

## Risks / Trade-offs

- [Old firmware with the new app, or the reverse, never confirms the zero] → Flash the firmware together with the app update; the README says so and `#H` is the only link between the two versions.
- [The contract test is textual, so it can be satisfied by a string that is never sent] → It checks the full reply literals; the angle filter and the real I2C behaviour stay manual-verification tasks on the hardware.
- [The `Mensagem:` line now shows `Z: OK`, less readable than `Zero definido`] → Accepted; the state line (`Conectado, zerado`) already carries the human meaning.
- [A `#C` that never replies `OK`] → The existing 10 s calibration limit applies unchanged.

## Migration Plan

1. Update the specs, the app, the tests and the firmware in one change.
2. Flash the new firmware, then run the app; on the bench check `#Z`, `#R`, `#C` answers on a serial terminal and the Settings screen messages.
3. Rollback: revert the change and reflash the previous firmware.
