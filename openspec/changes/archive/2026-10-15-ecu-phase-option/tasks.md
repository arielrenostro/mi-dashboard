## 1. Protocol constants and shared state

- [x] 1.1 Add `EcuCommand.PARAMETERS_X02 = ("#X02", ...)` and `EcuResponse.PARAMETERS_X02 = "#X02"` in `app/masterinjection/protocol.py`, plus `X02_PHASE_INDEX = 11`, a `Phase` enum (`NEGATIVE = 0`, `POSITIVE = 1`) and two pure helpers: parse an `#X02` line into 16 ints (or `None` when it is not exactly 16 integers) and return a copy of a block with only the phase replaced. Verify with `tests/test_phase_write.py` (parse valid / 15 values / non-numeric, only position 11 changes, the other 15 values are identical, input list not mutated) and `tests/test_ecu_connection_serial.py` (`#X02` without args is written as `#X02\n`, with 16 args as `#X02;v1;...;v16\n`, through `FakeSerial` and the command queue).
- [x] 1.2 Add `EventType.PARAMETER_BLOCK` in `app/state/event.py`, and `VehicleState.get_x02()` (copy or `None`) / `set_x02()` (ignored unless 16 values, emits the event) in `app/state/state.py`. Verify with new tests in `tests/test_vehicle_state.py`: never received, wrong length (no event), replacement, copy returned, event emitted with the 16 values.

## 2. Mock source

- [x] 2.1 In `app/ecu_connection/mock_log.py`, keep an initial `#X02` block (the `#X02` line of `65lbs - 32 - download - neg.csv`, phase 0), answer `#X02` without args with `#X02;...` on the emitter, store 16-arg writes silently, ignore other argument counts. Verify with new tests in `tests/test_ecu_connection_mock.py`: request, write-then-request, write is silent, wrong argument count, replay unaffected.

## 3. Phase write controller

- [x] 3.1 Create `app/ui/options/__init__.py` and `app/ui/options/phase_write_controller.py` (`PhaseWriteController`, QObject): 1000 ms single-shot debounce, request `#X02` when it elapses, handle `#X02` answers by prefix, build the write with only the phase replaced, queue the confirmation request, 2000 ms answer timeout, invalid-answer handling, "already applied" shortcut, toggle while in progress restarts the sequence, never sends `#D04`, publishes every valid line to the shared state, exposes the displayed phase and the status text and a `changed` signal. Inject `send_command`, state access and timers' intervals so tests need no ECU.
- [x] 3.2 Write `tests/test_phase_write.py` covering every scenario of `openspec/specs/phase-write` (as changed by this change): burst of toggles, request first, fresh block used, negative→positive and positive→negative using the sample `#X02` lines, toggled back (only the request is queued), no `#D04` in a complete sequence, applied / not applied after confirmation, unrelated line ignored, refresh without a change, wrong value count, non-numeric value, invalid confirmation, read timeout, confirmation timeout, toggle after the write. Drive timers with `timer.timeout.emit()`. Verify the file passes.

- [x] 3.3 Add the write sound: `PhaseWriteController` gets an optional `on_written` callback called once after the block is queued (not for requests, "already applied" or failures). Verify with new tests in `tests/test_phase_write.py` for each scenario of the "Write sound" requirement.

## 4. Options screen

- [x] 4.1 Create `app/ui/options/screen.py` (`OptionsScreen`, subclass of `Screen`): black background, title `Opções`, field rows (`Fase` for now) with the Home-style selected highlight, status line, hint `↑↓ Navegar | Enter Alterar | Esc Voltar`; ↑/↓ wrap, Enter/Return toggles via the controller (ignored when the phase is unknown), auto-repeat ignored, ESC calls `close_fn`; `on_activated` queues the `#X02` request unless a change is in progress; follows `vehicle_state.emitter` for the `PARAMETER_BLOCK` event; `on_ecu_line(line)` forwards to the controller. Mutes nothing and plays no sound.
- [x] 4.2 Write `tests/test_options_screen.py` covering every scenario of `openspec/specs/options-screen`: initial content, negative / positive / unknown / unexpected phase display, `Positiva …` while in progress, toggle, toggle twice, unknown phase ignores Enter, held key, ↓ with a single field, status texts for success and kept failure, request on activation and none during a change, ESC to Home (via `close_fn`), leaving during the delay still writes. Verify the file passes.

- [x] 4.3 `OptionsScreen` plays `config.ve_calibration.ve_sound` (restarting it) through `on_written`, also while hidden. Verify with tests in `tests/test_options_screen.py` that the player restarts on a write, that the screen leaving does not mute it, and that requests do not play it.

## 5. Navigation, shortcuts and wiring

- [x] 5.1 In `app/ui/home/screen.py` add the fourth menu item `("Opções", "options")`. Update `tests/test_screen_navigation.py`: menu content and order, the `Opções` entry opens `options`, the wrap tests still hold with four items.
- [x] 5.2 In `app/ui/window.py` register `options` (screen with `close_fn=lambda: self.show_screen("home")`), add `on_ecu_line(line)`, and handle F1-F4 in `keyPressEvent`/`keyReleaseEvent` before routing (consume, ignore auto-repeat, no-op for the visible screen, not announced). Leave `_DATA_SCREENS` unchanged. In `main.py` connect `get_ecu_connection().emitter` to `app_window.on_ecu_line`. Update `tests/test_window.py`: five registered screens, F1/F2/F3/F4 from Home and from other screens, shortcut of the visible screen is a no-op (no lifecycle hooks), held shortcut switches once, shortcut not delivered to the screen and not announced, release not delivered, ESC from `options` returns to Home, Enter on `options` is not announced, a `#X02` line passed to `on_ecu_line` reaches the Options screen.
- [x] 5.3 Verify `main.py` wiring by reading it back (it cannot be unit tested without a running event loop): the connection emitter is connected to `app_window.on_ecu_line` next to the other connections.

## 6. Documentation

- [x] 6.1 Update `README.md`: the Options screen (feature list and a short section about the phase and that it is not saved to memory), the Home menu, ESC list, and the keyboard table with F1-F4, Enter and ↑/↓ on Options. Update `CLAUDE.md`: code layout (`app/ui/options/`) and the capability list (`options-screen`, `phase-write`). Verify by re-reading both files.

## 7. Manual verification (hardware, cannot be unit tested)

- [x] 7.1 On the car or bench ECU, with the serial source and the engine off or at idle: open Options (F4) and confirm `Fase` shows the phase the ECU holds (compare with the vendor software); press Enter, wait ~1 s, confirm `Fase aplicada (não gravada na memória)`, read `#X02` back in the vendor software and confirm only the phase value changed (compare the whole line with the one saved before); toggle back; power-cycle the ECU and confirm the phase returns to the stored one (proof that `#D04` was not sent); confirm the ECU answers `#X02` while streaming without disturbing the telemetry; confirm the beep plays when the phase is written (and not on the reads). If it does not answer, record it in design.md (decision 4 and the first risk) and revisit the plan.
- [x] 7.2 With the mock source (`connection.mock` set): open Options with F4, toggle with Enter, check the status line, check F1-F4 from every screen and that Enter on Options does not play the mark sound (audio and the real screen cannot be unit tested).

## 8. Final check

- [x] 8.1 Run the full suite (`.venv-wsl/bin/python -m pytest` in WSL or `.venv\Scripts\python -m pytest` on Windows) and verify it passes, then run `openspec validate ecu-phase-option --strict`.
