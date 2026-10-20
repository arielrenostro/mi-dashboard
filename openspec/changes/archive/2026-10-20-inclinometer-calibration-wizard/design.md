## Context

The six-position accelerometer calibration lives in the firmware (`#K…` commands, see `inclinometer-firmware`, "Accelerometer calibration") and is driven today from a serial terminal. The app side is `app/gyro/` (`protocol.py` parser and command list, `state.py` thread-safe state, `connection.py` serial thread and `zero()`) and `app/ui/settings/screen.py` (a list of rows, a 200 ms refresh timer, a status line). See proposal.md - Why.

What the device does, read from the firmware:

- Each capture command blocks the device loop for about 0.5 s (100 samples, 5 ms apart), then answers `#K<axis><sense>;OK;`. The data stream pauses for that time, under the app's 1 s no-signal rule.
- The sixth distinct capture triggers the computation. A good result prints `#M;CALIBRACAO_SALVA;` then the report `#K;OFFSET;…;SCALE;…;`; a bad one prints `#M;CALIBRACAO_INVALIDA_REPITA_AS_POSICOES;` and discards the captures. Both come after the sixth acknowledgement.
- The captured-positions mask in the firmware is cleared only by a finished calibration or by `#KR`. A wizard that is cancelled halfway leaves a prefix of captured positions in the device.
- The device keeps `pitchZero` / `rollZero` (set by `#Z`) across a calibration. They were measured with the old offsets, so after a new calibration the zero is stale.
- `#KP` and `#KR` answer `#KP;OK;` / `#KR;OK;` followed by the report line.

This change depends on `inclinometer-accel-only`, which introduces the `#K` commands in the firmware and the requirements modified here (`Zero flag`, `Zero command`, `Settings screen layout`, `Inclinometer readout`). `openspec validate` accepts the deltas, but archiving is refused until that change is archived (it reports the missing requirements). Its hardware check (task 6.1) also proves the `#K` commands the wizard drives.

## Goals / Non-Goals

**Goals:**
- Calibrate from the Settings screen with the same six commands, without a terminal and without freeing the port.
- Show what the device ended up with (the report), and let the user print and restore it.
- Never leave a stale zero behind a calibration.

**Non-Goals:**
- Any firmware change. The device-side stale zero and the stale partial captures are handled in the app (clear `zeroed`, always walk all six steps).
- A speed guard: the calibration is a bench operation with the board in the hand, and the ECU's VSS says nothing about it.
- Validating the quality of the six positions in the app (the device checks the gains).
- A new setting in `config.json`: the calibration lives in the device's EEPROM.

## Decisions

1. **Calibration progress lives in `GyroState`, not in the wizard.** The state already folds every device line into thread-safe fields and announces changes. It gains the set of acknowledged capture commands, the outcome (`saved` / `invalid` / none) and the latest report, exposed in the snapshot. The wizard only reads the snapshot. Alternative: the wizard parses lines itself, rejected because the connection thread owns the lines and the screen would need a second subscription path; also the report line must reach the readout when no wizard is open (`Ver calibração`).

2. **The outcome comes from the `#M` texts, the report from the `#K;OFFSET` line.** There is no `#K…;OK` acknowledgement for the final result, only the two messages. The two texts are the only `#M` texts that act on state, which `Device messages` now says explicitly. The acknowledgement of the sixth capture clears the outcome (a new run starts) and the outcome clears the acknowledged set, so the wizard never has to remember anything the state does not already say.

3. **A wizard controller separate from the widgets.** A small class (`CalibrationWizard`, `app/ui/settings/calibration.py`) holds the step, the phase (waiting / capturing / calculating / done) and the deadlines, and is driven by three calls: `confirm()` (Enter), `cancel()` (Esc) and `update(snapshot, now)` (the 200 ms timer). It sends through the gyro object passed in and takes the clock as a parameter, so unit tests walk the whole flow with a fake gyro and a fake clock without Qt. `SettingsScreen` only draws the wizard and routes keys while one is open. Alternative: put the flow in `SettingsScreen`, rejected because that file already mixes rows, ports and numeric editing and the flow has timeouts worth testing alone.

4. **Step progress is read from the device's acknowledgements, never assumed.** The wizard advances when the step's command is in the snapshot's acknowledged set. A step whose acknowledgement does not arrive in 3 s (the capture takes 0.5 s) goes back to waiting with a message and the same Enter retries; capturing the same position twice is harmless on the device. The 3 s timeout covers a lost command, a device that restarted (the stream would also show `#H`) and a capture that failed with `FALHA_DE_LEITURA_DO_SENSOR`, without parsing that text.

5. **Always six steps from step 1, in a fixed order.** A cancelled run leaves a proper prefix of the order (`#KZU`, `#KZD`, `#KXU`, `#KXD`, `#KYU`, `#KYD`) captured in the device, never the whole of it, because the whole would have computed and cleared the mask. So the device's mask can only fill when `#KYD`, the last step, is captured, and by then the other five were recaptured in this run: no stale value reaches the computation. Alternative: send `#KR` first to clear the mask, rejected because it also wipes the stored calibration, and a cancelled wizard would then leave the module uncalibrated.

6. **`zeroed` is cleared by `CALIBRACAO_SALVA` and by `#KR;OK`.** The device keeps its pitch/roll zero across both, which was taken with the old offsets. Showing `Conectado, zerado` over a stale zero would make the ignition analysis trust a wrong inclination. The cost is one extra `Zerar inclinação` after every calibration, which the wizard's final screen could prompt for (it shows the report; the readout state line already says `Conectado, sem zero`). An invalid calibration changes nothing in the device, so it keeps the flag.

7. **Restore asks for a second Enter; view and open do not.** `#KR` overwrites the EEPROM with offset 0 and gain 1, which is exactly the uncalibrated state that made the old firmware drift. A second Enter on the same row, with any other key disarming, is the lightest guard. No timer: the screen has no modal, and an armed state that dies on any other key press is easy to test and hard to trigger by accident. Alternatives: a modal confirmation (more UI for a rare action) and no confirmation (the destructive command sits one Enter away).

8. **The calibration readout is a sixth line under the existing five, after the message line.** The five existing lines keep their indices, so the tests and the code that read them by position stay valid. It shows the latest report whatever produced it (wizard, `Ver calibração`, `Restaurar calibração`); it is empty (`--`) after a new connection until a report arrives, because the device does not send one by itself at boot. The wizard's final screen shows the same line.

9. **Command set of the connection.** `protocol.COMMANDS` lists the nine commands, the parser accepts a reply for each one (`#Z` and the `#K…` family) and the connection exposes `zero()`, `capture(position)`, `request_calibration()` and `restore_calibration()`, each returning False when the port is not open, like `zero()` today. The contract test already reads the firmware as text; it additionally checks that every command the app can send is one the firmware recognises.

## Risks / Trade-offs

- [The user moves the board before the capture finishes (0.5 s) and the position is averaged wrong] → The instruction says to keep it still; the device's gain range check rejects the grossly wrong runs and the report line shows the numbers for a sanity check.
- [A cancelled run leaves partial captures in the device] → Decision 5: every run recaptures all six; the worst case is a calibration computed from six captures that the user took in the order shown, as intended.
- [The data stream pauses about 0.5 s during each capture, close to the 1 s no-signal limit] → Still under it (a documented guarantee of `inclinometer-firmware`); even if the state shows `Sem sinal` for a moment, the wizard reads the acknowledgements, not the data stream.
- [A calibration while connected clears `zeroed`, so the ignition analysis stops using the inclination until the user zeroes again] → Intended: the old zero would be wrong; the screen shows `Conectado, sem zero` straight away.
- [Pressing Enter on `Ver calibração` with an old firmware that does not know `#KP`] → The device answers `COMANDO_DESCONHECIDO`, which shows on the message line; nothing else happens.
- [Two different programs on the same port] → Not applicable any more: the wizard uses the app's own connection, the point of the change.

## Migration Plan

1. Archive `inclinometer-accel-only` first (after its hardware check).
2. Land this change (app, tests, docs) in one commit; no firmware flash is needed.
3. Manual check on the module: run the wizard, compare the report with `#KP` in a terminal, run the wizard with a deliberately wrong position to see `Calibração inválida`, restore and calibrate again.
4. Rollback: revert the commit. The calibration stored in the EEPROM is untouched by the app's code.

## Open Questions

- Whether the wizard's last screen should also offer `Zerar inclinação` directly (one more key) instead of only leaving the user on `Conectado, sem zero`. Not needed for the specs; decide while looking at it on the screen.
