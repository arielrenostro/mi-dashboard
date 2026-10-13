## 1. Configuration

- [x] 1.1 Add `mark_sound` (default `alarm.wav`) to the datalog config in `app/config.py` and verify it loads and defaults correctly

## 2. Wiring

- [x] 2.1 Add a key-press signal to `AppWindow` emitted for non-repeating presses only while the Dashboard or VE screen is active, and verify it is not emitted on Home or for auto-repeat
- [x] 2.2 Create `EventMarker(config.datalog.mark_sound)` in `main.py`; connect the window signal to it and its event signal to the log writer's pending-mark method
- [x] 2.3 Run with the mock, press Enter on the Dashboard and verify the next row of the new CSV has `MARK` and the following row does not; verify Enter on Home still opens a screen and writes no mark; verify holding Enter marks once

## 3. Documentation and verification

- [x] 3.1 Document `datalog.mark_sound` and the Enter shortcut in the README
- [x] 3.2 Run `openspec validate wire-event-marker --strict` and verify it passes

## 4. Unit tests

- [x] 4.1 Create `tests/test_event_marker.py` (player replaced by a mock): Return and Enter play the sound from the start and emit the event; other keys do nothing
- [x] 4.2 Extend `tests/test_window.py`: the key signal is emitted on the Dashboard and VE screens, not on Home, and not for auto-repeat
- [x] 4.3 Cover marker to log writer in `tests/test_event_marker.py` (real window, marker and log writer: exactly one `MARK` row for several presses before a frame, for held Enter, and none for Enter on Home); extend `tests/test_app_configuration.py`: `datalog.mark_sound` default and loading
- [x] 4.4 Run the full suite (`python -m pytest`) and verify it passes
