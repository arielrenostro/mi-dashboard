## Why

The ignition tuning screen only analyses one gear (`ignition_tuning.gear`, default 5). On the road it is not always possible to hold the RPM band in 5th, but 4th would do, and today every sample taken in 4th is thrown away. The same advance offsets should be testable in 4th and 5th in the same session, keeping what was learned in each gear, and the results should survive the session on disk.

## What Changes

- The analysis keeps one set of scenarios per gear: a scenario is identified by `(gear, offset)`. Percentage differences, the best scenario and the "discard worst" action are computed inside one gear, because the same RPM band in two gears is a different operating point. The advance offset itself stays global.
- `ignition_tuning.gear` becomes `ignition_tuning.gears`, a list of gears to analyse (default `[5]`, so behavior without configuration does not change). **BREAKING** for a `config.json` that sets `ignition_tuning.gear`: the key is no longer read.
- The screen shows the scenarios of one gear at a time. It follows the engaged gear while that gear is one of `gears`, keeps the last shown gear otherwise, and ←/→ switch the shown gear manually (to review the other gear while stopped). The top bar shows which gear is shown and whether the other gears already hold data.
- The top bar gets a second line with CLT, IAT, the shown gear indicator and the analysed RPM band. The RPM band is removed from the scenario columns, where it was redundant.
- X discards the worst scenario of the shown gear only. R clears every gear.
- Results are saved to a CSV in `datalog.path` (one row per gear and offset, including discarded scenarios flagged as such). The file is rewritten while results change, on leaving the screen, on reset and on shutdown; reset closes the file and the next valid sample starts a new one.

## Capabilities

### New Capabilities
- `ignition-results-log`: the CSV snapshot of the ignition analysis results: file naming and lifetime, columns, discarded scenarios, when it is rewritten and how write failures are handled.

### Modified Capabilities
- `ignition-analysis`: scenarios are keyed by gear and offset; the gear condition is "one of the configured gears"; statistics, eligibility, percentage differences, best scenario, ready notification and discard are per gear; discarded scenarios are kept for the results log; reset clears every gear.
- `ignition-tuning-screen`: shown gear (follow, manual switch, indicator), second top-bar line with CLT, IAT, shown gear and RPM band, no RPM band in the columns, X acts on the shown gear, new footer hint for ←/→.
- `app-configuration`: `ignition_tuning.gears` replaces `ignition_tuning.gear`.
- `app-lifecycle`: shutting down flushes the pending ignition results.

## Impact

- Code: `app/ui/ignition_tuning/analysis.py` (key by gear, per-gear statistics, discarded list), `app/ui/ignition_tuning/screen.py` (shown gear, top bar, columns), a new results writer next to the screen, `app/config.py` (`gears`), `app/ui/window.py` (flush on close), `config.json`.
- Tests: `tests/test_ignition_analysis.py`, `tests/test_ignition_tuning_screen.py`, `tests/test_app_configuration.py`, `tests/test_app_lifecycle.py`, and a new `tests/test_ignition_results_log.py`.
- Docs: `CLAUDE.md` code layout and the README key list.
- No protocol, ECU or signal changes: CLT and IAT already exist in the signal catalog.
