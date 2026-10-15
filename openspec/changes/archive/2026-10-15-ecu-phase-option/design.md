## Context

See proposal.md for motivation. Today:

- Commands go through `get_ecu_connection().send_command(cmd, args)`, are queued and written after the next complete telemetry frame or after a non-telemetry line (spec `ecu-connection`, "Command queue").
- While streaming, every line that is not `#D01`/`#D02` is emitted unchanged on the connection's `emitter` (`EcuConnectionSerial.run`). `SignalProcessor` ignores everything but `#D01`, and nothing else listens, so an answer to `#X02` would be dropped today.
- VE and ignition writes are debounced by `RowWriteController` (fire and forget, one command per pending row). The phase write is different: it needs a **read-modify-write** because `#X02` carries 15 other values the app must not touch.
- `AppWindow` routes keys only to the visible screen; `_DATA_SCREENS` decides which key presses are announced to the event marker (Enter marks the data log). The Options screen is not a data screen.
- The phase position was found by diffing `65lbs - 32 - download - neg.csv` and `... - pos.csv`: the only different line is `#X02`, position 11 (0-based), `0` in the negative map and `1` in the positive one.

## Goals / Non-Goals

**Goals:**
- Change the phase from the car, repeatedly, without saving it to the ECU memory and without touching any other `#X02` value.
- Show what the ECU really holds, including after the write.
- Leave room for more fields on the Options screen (list of rows with one selected row).
- F1-F4 reach any screen from any screen.

**Non-Goals:**
- Editing any other `#X02` value, or any other parameter block (`#X01`, `#X03`...).
- Persisting to memory (`#D04`) from the app.
- Reading `#X02` during the serial handshake (see decision 4).
- Configurable shortcut keys.

## Decisions

1. **A dedicated `PhaseWriteController` (QObject) with injected callables, not a reuse of `RowWriteController`.** `RowWriteController` dispatches pending rows and beeps; the phase flow is a small state machine (IDLE → PENDING → READING → VERIFYING). It takes `send_command`, `get_block`/`set_block` (shared state) and two `QTimer`s (1000 ms debounce, 2000 ms answer timeout), so tests drive it with a recorder and `timer.timeout.emit()`, as `tests/test_ve_write.py` does. *Alternative:* generalise `RowWriteController` — rejected, the read-before-write has nothing in common with row dispatch.

2. **Answers reach the controller through the window.** `main.py` connects the connection's `emitter` to a new `AppWindow.on_ecu_line(str)`, which forwards to the Options screen's controller. The signal crosses from the connection thread to the main thread by Qt's queued connection, so the controller and the UI stay on one thread. The controller handles only lines starting with `#X02`. *Alternative:* parse in `EcuConnectionSerial` — rejected, it would couple the connection to a UI feature and the mock would need its own copy.

3. **The controller outlives the screen being visible.** The screen creates it and it keeps its timers, so leaving the screen within the 1 s delay does not cancel the write (spec `options-screen`, "Leaving the screen"). The screen only renders `displayed phase` and the status text, which the controller exposes through a `changed` signal.

4. **First `#X02` is requested when the Options screen is activated, not in the handshake.** `_send_and_retry` loops without a bound until the ECU answers; an unverified `#X02` answer during the handshake could keep the whole connection in HANDSHAKE. A request on activation fails softly (`Sem resposta da ECU`) and also refreshes the value when it was changed by other means. *Alternative:* fetch with the VE/ignition maps — simpler wiring, but riskier; can be revisited once the manual check (task 7.1) shows the ECU answers `#X02` reliably.

5. **Phase meaning lives in `protocol.py`** (`X02_PHASE_INDEX = 11`, `Phase` enum with `NEGATIVE = 0`, `POSITIVE = 1`), next to the command definitions, plus a pure helper that parses an `#X02` line into 16 ints (or `None`) and one that returns a copy of a block with only the phase replaced. Both are pure functions, so the "only the phase changes" requirement is tested without Qt.

6. **Shared state stores the block as `list[int] | None`** and `get_x02()` returns a copy, because the controller mutates a copy to build the write. A new `EventType.PARAMETER_BLOCK` event announces changes; the screen listens to `vehicle_state.emitter` as the VE screen does. Only valid lines are published.

7. **Verification read after the write.** The app queues `#X02` again right after the write and compares. The ECU processes serial lines in order, so the answer reflects the write. This tells the driver the truth ("applied" or "the ECU kept ..."), which matters for a setting that changes how the engine starts. Cost: one more short command per change.

8. **Window-level shortcuts.** `AppWindow.keyPressEvent` and `keyReleaseEvent` check a `{F1..F4: screen name}` map first; a shortcut key is consumed (never delivered to the screen, never announced as `key_event`), auto-repeat is swallowed, and the key of the visible screen is a no-op so the lifecycle hooks do not fire twice. `_DATA_SCREENS` stays unchanged, which is what keeps Enter on Options from marking the data log. The window-level check also works on Home. `Options` is added to the Home menu and to `AppWindow._register_screens`.

9. **Mock.** `EcuConnectionMock.send_command` answers `#X02` (no args) with its kept block and stores 16-argument writes silently. Initial block = the `#X02` line of the negative map, so phase starts as Negativa.

10. **Write sound.** `PhaseWriteController` takes an `on_written` callback, called right after the write command is queued; `OptionsScreen` supplies one that restarts a `QMediaPlayer` loaded with `config.ve_calibration.ve_sound` (no new config key, not muted when the screen is hidden because the write can happen after leaving it). The scope is only the phase write, as VE/ignition/lambda already have their own sounds; reads stay silent.

## Risks / Trade-offs

- [The ECU may not answer `#X02` while streaming (not verified; the user states the command can be sent)] → the screen shows `Sem resposta da ECU` and nothing is written; manual check on the car (task 7.1) before relying on it.
- [Writing the whole block replaces the 15 other values with what was just read; a change made elsewhere in between would be lost] → the read happens immediately before the write (a few frames apart), and the block comes from the answer, not from a stored copy.
- [A write issued while the serial link is down is queued but never sent] → the read times out first (2 s) and nothing is written.
- [Queued commands are written only after a telemetry frame or other line] → up to one frame of latency; well inside the 2 s timeouts.
- [Phase value other than 0/1 reported by the ECU] → shown as `—` and Enter is disabled, so the app never overwrites an unknown encoding.
- [F-keys are also used by some terminals/remote tools] → not an issue for the full-screen Qt window; documented in the README.
