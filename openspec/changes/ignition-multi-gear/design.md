## Context

See proposal.md for the motivation. Today `IgnitionAnalysis` keeps `scenarios: Dict[offset, _Accumulator]`, filters on one configured gear (`ignition_tuning.gear`), and the screen draws one column per scenario, each column repeating the RPM band. Settling, pause, the lambda-loop tracking and the write handshake are properties of the whole analysis, not of a scenario, and the advance offset lives in `IgnitionMapState` and is global. The datalog (`LogWriter`) is a separate thread-backed append-only writer for raw frames; it is not suited to a file that is rewritten as a snapshot.

## Goals / Non-Goals

**Goals:**
- Accumulate scenarios per `(gear, offset)` in the same analysis, compare only inside a gear.
- Show one gear at a time, following the engaged gear, with a manual switch.
- Keep every result, including discarded scenarios, in a CSV that survives resets and the end of the session.

**Non-Goals:**
- A per-gear RPM band or per-gear offsets (the offset stays global, the band is shared).
- Loading earlier results back into the app: the CSV is an output only.
- Persisting the analysis state itself (the screen still starts empty).
- Comparing gears with each other.

## Decisions

**One analysis, composite key.** `_scenarios` becomes `Dict[(gear, offset), _Accumulator]`, and the sample filter checks `gear in self.gears`. Alternative: one `IgnitionAnalysis` per gear. Rejected: pause, resume, settling, the write handshake and lambda-loop tracking would be duplicated and have to be fanned out to every instance, and a gear change would need extra coordination to stay a non-event for settling.

**Gear change ends the continuous run.** The previous-sample tuple becomes `(time, knock, offset, gear)` and time and knock are only accumulated when offset and gear both match. This also keeps the knock counter from being compared across a shift. No settling is added on a gear change, because a shift already opens the lambda loop, which the existing tracking turns into settling.

**Queries per gear.** `scenarios(gear)` returns the active scenarios of one gear with `diff` and `is_best` computed inside that gear; `gears_with_data()` lists gears with at least one active scenario; `discard_worst(gear, current_offset)` acts on one gear. `ScenarioStats` gains `gear` and `discarded`. The shared best/diff computation is one private function over a list of accumulators, so the per-gear queries and the snapshot for the CSV use the same code.

**Discarded scenarios are moved, not deleted.** Discarding takes the accumulator out of `_scenarios` (so everything downstream keeps treating it as gone, and the next sample at that gear and offset starts from zero) and appends its final `ScenarioStats(discarded=True)` to a `_discarded` list that only `reset()` clears. The same key can appear several times there.

**Shown gear is view state.** It lives in `IgnitionTuningScreen`, not in the analysis: the analysis keeps sampling the engaged gear regardless of what is displayed. The screen remembers the last engaged gear it saw and changes the shown gear only when that engaged gear changes to a configured gear, which is what lets a manual ←/→ choice last until the next shift. The initial shown gear is the highest configured gear.

**Results log as its own object.** A new `IgnitionResultsLog` (`app/ui/ignition_tuning/results_log.py`, no Qt) owns the run: it knows the analysis, the directory, a wall clock (for the file name) and a monotonic clock (for the 5 s limit), both injectable. The analysis exposes a `revision` counter that increases on every accepted sample, discard and reset, so the log can tell "changed" without diffing rows.
- `tick()` is called after each telemetry set the screen analyses. It writes when the revision changed and at least 5 s passed since the last attempt. The first accepted sample of a run starts the run (path from the wall clock) and writes immediately.
- `flush()` writes if the revision changed since the last successful write, ignoring the interval. It is called when the screen is deactivated and on window close.
- `end_run()` flushes, then forgets the path, so the next accepted sample starts a new file. The screen calls it in the reset handler before clearing the analysis.
- A write builds the full snapshot (active scenarios of every gear ordered by gear and offset, each followed by its discarded twins, with `diff` and `best` empty or `0` for discarded rows), writes it to `<name>.tmp` in the same directory and replaces the target with `os.replace`. A failure is caught, logged (the first failure of a streak at warning level, later ones at debug) and counts as an attempt for the 5 s limit, so a broken directory is retried at the normal rhythm rather than on every sample; the previous snapshot is untouched.
Alternatives: append-only rows per event (would need the same bookkeeping to flag discards and cannot hold means that keep changing) and routing the snapshot through `LogWriter`'s thread (the file is a few dozen rows rewritten at most every 5 s, so a thread adds more machinery than the work it would hide).

**Flush on window close.** `AppWindow` overrides `closeEvent` to call the ignition screen's flush; `shutdown()` already calls `window.close()` first. Closing the window from Home with ESC reaches the same code, and the later `close()` in `shutdown()` finds nothing changed, so the flush is idempotent.

**Config.** `AppConfigIgnitionTuning.gears` replaces `gear`; the old key is simply not read (personal project, one `config.json`). A value that is not a non-empty list of integers falls back to the default `[5]`. `config.json` is updated to `[4, 5]`.

**Top bar layout.** The bar becomes a left block with two lines and the existing offset and status block on the right spanning both lines. Line 1 keeps the six `SignalCard`s; line 2 holds CLT and IAT `SignalCard`s, the gear indicator and the band label. The band moves out of `ScenarioColumn` (the `band` row and the `band` parameter are removed), which frees vertical space for the extra line.

## Risks / Trade-offs

- [Two top-bar lines plus the columns may not fit the in-car screen] → the cards keep the Dashboard's `SignalCard` fonts on both lines (nothing is shrunk); check on the mock source and on the car (manual task).
- [A manual ←/→ choice made while driving hides the engaged gear's columns until the next shift] → the gear indicator keeps showing which gear is engaged-and-holding-data; the footer lists the keys; the shown gear returns to the engaged one on the next shift.
- [The results file open in a spreadsheet blocks `os.replace` on Windows] → the write fails, is logged once per streak and is retried; the data is not lost because the analysis keeps everything in memory.
- [Snapshot write on the UI thread] → bounded by the 5 s rate limit and a few dozen rows; the forced flushes happen at moments the user is not driving the screen. If a slow disk ever shows, the writer is one class that can move to a thread without touching the spec.
- [`datalog.path` default is not a usable directory (known issue)] → writes fail softly as above; the screen works without the file.
- [A run's file stops updating after R] → intended: R closes it and the next run gets a new name.

## Migration Plan

Update `config.json` to `ignition_tuning.gears: [4, 5]` (remove `gear` if present). No data migration: results files are new. Rollback is reverting the change; the CSVs written meanwhile stay on disk and are not read by anything.
