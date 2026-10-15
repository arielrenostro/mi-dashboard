## Why

The car picks the correct crank/cam phase only about half of the time when it starts, and today the only way to change the phase is the vendor software on a PC. The ECU accepts the phase through the `#X02` parameter block, so the dashboard can flip it at any time, from the driver's seat, without saving it to the ECU memory.

## What Changes

- New **Options** screen with a list of fields. For now it has a single field, **Fase**, showing `Negativa` or `Positiva`. Enter toggles the value of the selected field.
- Changing the phase is debounced by 1 s (same idea as the VE and ignition writes). When the delay elapses the app asks the ECU for `#X02`, replaces **only** the phase value in the answer and writes the whole block back with `#X02;...`. The write-on-memory command `#D04` is **not** sent, so the change lasts until the ECU is power-cycled. The app then reads `#X02` again to confirm what the ECU actually holds. The write plays the VE confirmation sound (`ve_calibration.ve_sound`).
- The phase is the 12th value of `#X02` (position 11, 0-based): `0` = Negativa, `1` = Positiva. Found by comparing the maps `65lbs - 32 - download - neg.csv` and `65lbs - 32 - download - pos.csv`: the only different line is `#X02`, and only in that position (`...;1750;0;1960;...` vs `...;1750;1;1960;...`).
- The latest `#X02` block is kept in the shared vehicle state, and the screen follows it.
- Home gets a fourth menu entry, `Opções`, and the new screen returns to Home with ESC.
- **Global shortcuts**, valid on every screen including Home: **F1** Dashboard, **F2** VE calibration, **F3** Ignition tuning, **F4** Options. The shortcut keys are handled by the window and are not delivered to the screen.
- The mock source answers `#X02` requests and remembers `#X02` writes, so the screen can be exercised without hardware.

## Capabilities

### New Capabilities
- `options-screen`: the Options screen: field list, keyboard navigation, the phase field, its display states and status messages.
- `phase-write`: how a phase change reaches the ECU: debounce, read-modify-write of `#X02`, no write to memory, confirmation read, failure handling.

### Modified Capabilities
- `screen-navigation`: a fifth screen (`options`), a fourth Home menu entry, ESC from Options, global F1-F4 shortcuts, keyboard routing exception for the shortcuts.
- `ecu-protocol`: `#X02` command and response, the position and meaning of the phase value.
- `vehicle-state`: holds the latest `#X02` block and emits a change event when it is set.
- `ecu-connection`: the mock source answers `#X02` requests and keeps `#X02` writes.

## Impact

- Code: `app/masterinjection/protocol.py` (`#X02` command/response, phase constants), `app/state/state.py` and `app/state/event.py` (X02 snapshot + event), new `app/ui/options/` (screen and phase write controller), `app/ui/home/screen.py` (menu entry), `app/ui/window.py` (register the screen, F1-F4, forward connection lines to the controller), `app/ecu_connection/mock_log.py` (answer `#X02`), `main.py` (wire the connection lines to the window).
- Tests: new `tests/test_options_screen.py` and `tests/test_phase_write.py`; updated `tests/test_screen_navigation.py`, `tests/test_window.py`, `tests/test_vehicle_state.py`, `tests/test_ecu_connection_mock.py` and, for the protocol constants, `tests/test_ecu_connection_serial.py`.
- Docs: README key table and screen list, `CLAUDE.md` code layout and the capability list.
- No new configuration keys and no new dependencies. The serial handshake is unchanged (see design: the first `#X02` is requested when the Options screen opens).
- Overlaps with the in-flight `ignition-multi-gear` change only in `app/ui/window.py` (a different area); no spec requirement is shared with it.
