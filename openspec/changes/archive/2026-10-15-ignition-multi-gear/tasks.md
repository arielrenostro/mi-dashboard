## 1. Configuration

- [x] 1.1 Replace `gear` by `gears` (list of ints, default `[5]`, non-list or empty falls back to the default) in `AppConfigIgnitionTuning`; update `tests/test_app_configuration.py` (defaults, configured `[4, 5]`, old `gear` key not read, invalid value falls back) and verify they pass
- [x] 1.2 Set `ignition_tuning.gears` to `[4, 5]` in `config.json` and verify the configuration tests still pass

## 2. Analysis per gear

- [x] 2.1 Key scenarios by `(gear, offset)`, accept any gear in `gears`, include the gear in the previous-sample tuple so a gear change ends the continuous run, and add `gear` and `discarded` to `ScenarioStats`; update the existing tests in `tests/test_ignition_analysis.py` to the new API and add the scenarios "Second configured gear", "Gear not configured", "Same offset in two gears", "Gear change without settling", "Gear change ends the run"; verify the file passes
- [x] 2.2 Compute percentage differences and the best scenario inside each gear (`scenarios(gear)`) and add `gears_with_data()`; add tests "Gears are independent", "One best per gear", "Gears holding data", "Reset" in `tests/test_ignition_analysis.py` and verify they pass
- [x] 2.3 Make the ready notification per gear and offset; add the test "Threshold reached in the other gear" to `tests/test_ignition_analysis.py` and verify it passes
- [x] 2.4 Make `discard_worst(gear, current_offset)` act on one gear, retain discarded scenarios until reset (`discarded()`), and add a `revision` counter bumped by accepted samples, discards and reset; add tests "Other gear untouched", "Discarded scenario retained", "Same key twice", "Discarded not compared", "Cleared by reset", and a revision test, in `tests/test_ignition_analysis.py`, and verify the whole file passes

## 3. Results log

- [x] 3.1 Implement `IgnitionResultsLog` in `app/ui/ignition_tuning/results_log.py` (run start on the first accepted sample, file name from an injectable wall clock, snapshot rows and header, atomic replace, 5 s limit from an injectable monotonic clock, `tick`, `flush`, `end_run`, soft failure with one warning per failure streak)
- [x] 3.2 Write `tests/test_ignition_results_log.py` with a temporary directory and fake clocks covering every scenario of the ignition-results-log spec (file name, nothing before a sample, reset starts a new file, reset without samples, header, active row, discarded row, not eligible row, gear order, same key twice, periodic rewrite, leaving the screen, final snapshot on reset, discard recorded, nothing changed, unusable directory, retry, failure keeps the previous snapshot) and verify the file passes

## 4. Screen

- [x] 4.1 Add the shown gear to `IgnitionTuningScreen` (initially the highest configured gear, follow the engaged gear when it changes to a configured gear, ←/→ without wrapping, ignored with one gear, auto-repeat ignored) and make the columns, the empty state, the best border and X (`discard_worst(shown_gear, offset)`) use the shown gear; R clears every gear; update the existing tests in `tests/test_ignition_tuning_screen.py` and add the scenarios of "Shown gear", "Only the shown gear", "Empty gear", "Best of the other gear", "Discard only in the shown gear" and the modified "Reset"; verify the file passes
- [x] 4.2 Rebuild the top bar as two lines (CLT, IAT, gear indicator, `Faixa <min>-<max>` on the second line, offset and status block on the right), remove the band row from `ScenarioColumn`, and add `←→ Marcha` to the footer; add the scenarios "Coolant and intake temperature", "Temperatures never received", "Analysed RPM band", "Gear indicator", "Single configured gear", "Column content" (no band), "Footer hints" to `tests/test_ignition_tuning_screen.py` and verify they pass
- [x] 4.3 Wire `IgnitionResultsLog` into the screen (`tick` after each analysed telemetry set, `flush` on deactivation, `end_run` before the analysis is cleared by R, `flush_results()` for the window); add screen-level tests in `tests/test_ignition_tuning_screen.py` (a sample creates the file in a temporary `datalog.path`, ESC flushes, R closes the file and the next sample opens a new one, X marks the row as discarded, a failing directory does not stop the analysis) and verify they pass

## 5. Shutdown

- [x] 5.1 Override `closeEvent` in `AppWindow` to flush the ignition results; add the scenario "Ignition results are kept" to `tests/test_window.py` (and keep `tests/test_lifecycle.py` passing) and verify they pass

## 6. Docs and verification

- [x] 6.1 Update `CLAUDE.md` (code layout, `ignition_tuning.gears`, the results file) and the README key list (←/→ and the results CSV); verify the text matches the specs
- [x] 6.2 Run the full suite (`.venv\Scripts\python -m pytest` on Windows, `.venv-wsl/bin/python -m pytest` in WSL) and verify it passes; clear `__pycache__` if a result looks impossible
- [x] 6.3 Manual check with the mock source (`connection.mock` set): open `Ajuste de Ignição` and confirm the two-line top bar fits and reads well, the gear indicator and the band show, ←/→ switch the shown gear, X and R behave as in the specs, and a results CSV appears in `datalog.path` and is closed by R (audio and the real screen size cannot be unit tested)
- [x] 6.4 Manual check on the car: take samples in 5th, shift to 4th and take samples at the same offsets, confirm each gear keeps its own columns, best border and percentages, open the results CSV in a spreadsheet and confirm one row per gear and offset, a discarded scenario flagged with `Discarded = 1`, and that leaving the file open does not break the screen
