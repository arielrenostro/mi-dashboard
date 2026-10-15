## 1. Signals, protocol and configuration

- [x] 1.1 Add `INJ_PULSE` (position 7, raw/100, ms) and `KNOCK` (position 11, integer) to the `Signal` enum; add scenarios to `tests/test_signal_model.py` (injection pulse conversion, knock counter, frame parsing still publishes every convertible signal) and verify they pass
- [x] 1.2 Add `IGN_ROW_1..16` (`#I01..#I16`) to `EcuCommand` and `EcuResponse`; extend `tests/test_ecu_connection_serial.py` (command with arguments written as `#I03;v1;...;v16`, response recognized) and verify they pass
- [x] 1.3 Add `AppConfigIgnitionTuning` (keys and defaults from the app-configuration spec, section `ignition_tuning`) to `app/config.py`; add tests to `tests/test_app_configuration.py` (defaults without the section, a configured band, partial section) and verify they pass
- [x] 1.4 Add an `ignition_tuning` section to `config.json` using existing files in `resources/` for the four sounds; verify the app config still loads (run the configuration tests)

## 2. Shared state and ECU connection

- [x] 2.1 Add the ignition map, `get_ignition_map`/`set_ignition_row` (same validation as `set_ve_map`, but with a correct index check) and an `IGNITION_MAP` event type to `vehicle_state`; add tests (wrong length ignored without event, valid row stored and event emitted with index and values) in a new `tests/test_vehicle_state.py` or the existing state tests, and verify they pass
- [x] 2.2 Add `_fetch_ignition_map` to the serial handshake, run after the VE rows and before streaming start; add tests with `FakeSerial` in `tests/test_ecu_connection_serial.py` (all 16 ignition rows requested and published before `#D01` streaming start, silent ECU re-sends) and verify they pass
- [x] 2.3 Make the mock source publish a fixed ignition map; add a test in `tests/test_ecu_connection_mock.py` (16 rows published on start) and verify it passes

## 3. Ignition map model

- [x] 3.1 Implement `IgnitionMapState` (original, offset, derived working map, loaded flag, affected rows from the MAP axis and `max_map_kpa`, ceiling, pending rows, mark sent, reset, row loading only at offset 0) in `app/ui/ignition_tuning/ignition_map_state.py`
- [x] 3.2 Write `tests/test_ignition_map_model.py` covering every scenario of the ignition-map-model spec (addressing, row replaced at offset 0, row ignored at offset ≠ 0, not loaded, raise, lower, floor and recovery, ceiling, limit row included, rows above the limit untouched, axis not loaded, pending rows after raise/sent/undone, reset with and without a loaded map) and verify the file passes

## 4. Analysis

- [x] 4.1 Implement `IgnitionAnalysis` and `ScenarioStats` in `app/ui/ignition_tuning/analysis.py` (valid sample conditions, settling with awaiting-write, resume and lambda loop closing again (tracked on every set), scenarios by offset, analysed time with the 1 s gap rule, means, knock increases per continuous run, eligibility, percentage differences, best scenario, pause/resume, ready notification, reset), driven only by explicit timestamps
- [x] 4.2 Write `tests/test_ignition_analysis.py` with one test per scenario of the ignition-analysis spec, feeding sets built with `tests/helpers.py` (`parsed`, `SAMPLE_FRAME`, `frame_with` through `SignalProcessor` where practical), and verify the file passes

## 5. Row write controller

- [x] 5.1 Extract `RowWriteController` into `app/ui/common/row_write_controller.py` (debounce timer, ascending pending rows, mark sent before queuing, sound, "write finished" hook called on every timer expiry); make `VeWriteController` delegate to it keeping its public name and constructor; run `tests/test_ve_write.py` unchanged and verify it still passes
- [x] 5.2 Add the ignition write wiring (command `IGN_ROW_N`, pending rows and values from `IgnitionMapState`, hook that tells the analysis the write finished) and tests in `tests/test_ignition_tuning_screen.py` for the ignition-write scenarios (burst of presses, rows written in order with 16 values, undone edit sends nothing, reset writes all 16 rows, `#D04` never sent) using a fake connection; verify they pass

## 6. Screen

- [x] 6.1 Implement `IgnitionTuningScreen` in `app/ui/ignition_tuning/screen.py` (top bar and status priority, scenario columns with percentages and best border, empty state, footer, 100 ms refresh that stops when hidden, key handling ignoring auto-repeat, sound cues, state kept while hidden, telemetry ignored while hidden); no code outside the specs' behavior
- [x] 6.2 Write the rest of `tests/test_ignition_tuning_screen.py` (offscreen Qt, fake connection and media players) for the ignition-tuning-screen spec: footer hints, each status label and its priority, column content and ordering, `--` for ineligible scenarios, best border present on exactly one column, key scenarios (raise, held key, map not loaded, pause toggle, reset, ESC), leave-and-return, hidden telemetry, refresh stop, write sound, ready sound, pause/resume sounds; verify the file passes

## 7. Navigation and datalog

- [x] 7.1 Register the screen in `AppWindow`, connect `signal_processor.emitter` to it, add `ignition_tuning` to the key-announcing data screens, and add the `Ajuste de Ignição` entry to Home; update `tests/test_screen_navigation.py` (four screens, Home menu order, entry opens the screen, ESC returns to Home) and verify it passes
- [x] 7.2 Add a scenario to `tests/test_event_marker.py` (or the window key tests) that Enter on the ignition screen marks the datalog, and verify it passes

## 8. Discard the worst scenario

- [x] 8.1 Add `discard_sound` to `AppConfigIgnitionTuning` and `config.json`; extend `tests/test_app_configuration.py` (default and loaded value) and verify it passes
- [x] 8.2 Implement `IgnitionAnalysis.discard_worst(current_offset)` and write one test per scenario of "Discard the worst scenario" in `tests/test_ignition_analysis.py`; verify they pass
- [x] 8.3 Add the X key, the discard sound and the footer hint to `IgnitionTuningScreen`; add tests in `tests/test_ignition_tuning_screen.py` (column removed, offset and ECU untouched, worst is current, nothing to compare, held key ignored, sound only when discarded, footer lists X); verify they pass

## 9. Verification

- [x] 9.1 Run the full suite (`.venv\Scripts\python -m pytest` on Windows, `.venv-wsl/bin/python -m pytest` in WSL) and verify it passes; clear `__pycache__` if a result looks impossible
- [x] 9.2 Manual check with the mock source (`connection.mock` set): open `Ajuste de Ignição`, press Up/Down/Space/R and confirm the screen, status labels and sounds behave as in the specs (audio output cannot be unit tested)
- [x] 9.3 Manual check on the car, offline first: with the engine running and the car stopped, read `#I01..#I16` and confirm the raw unit is whole degrees and the rows follow the `#F` row order; press Up and confirm the `IGN` telemetry changes by 1 at a fixed operating point, then R and confirm it returns; confirm `INJ_PULSE` is in units of 10 µs against the datalog and that `KNOCK` is a counter that only increases
- [x] 9.4 Update `CLAUDE.md` (code layout, `ignition_tuning` section name) and the README key list so they match the new screen
