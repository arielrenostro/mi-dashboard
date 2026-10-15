## Context

See proposal.md for motivation. Relevant current state:

- The VE calibration screen edits the fuel map cumulatively (`VeMapState.adjust_ve`) and writes pending rows through `VeWriteController` (1 s debounce, one `#F0N` command per row, no `#D04`). The serial handshake loads breakpoints and the 16 VE rows into `vehicle_state` and the screen reacts to `VehicleStateChangeEvent`s. The `#I20`/`#I21` breakpoints are shared by VE and (as confirmed with the user) ignition.
- Telemetry arrives as one parsed dict per frame from `SignalProcessor.emitter` (about 10 per second); `Signal` already has `RPM`, `MAP`, `PEDAL`, `GEAR`, `IGN`, `LAMBDA`, `LAMBDA_LOOP`. The frame also carries the injection pulse (position 7) and a knock counter (position 11), not yet in the catalog.
- The window forwards non-repeating key presses of data screens to the event marker (Enter marks the datalog). Space, R, Up, Down are free on a new screen.
- The user cannot look at the screen while driving: few keys, audible cues, large text.

## Goals / Non-Goals

**Goals:**
- Pure, Qt-free logic for the ignition map (original + offset) and the analysis, so every scenario of the specs is unit-testable without display, audio or hardware.
- A screen that is only a thin view over that logic plus key handling.
- Reuse the existing debounced row-by-row write instead of cloning it.

**Non-Goals:**
- No persistence to ECU memory (`#D04`), no export of the result, no "apply best offset" key (the user reads the best offset and sets it in the tuning software).
- No per-cell or per-RPM ignition editing; no multiple RPM bands in one session.
- No automatic knock protection (the counter is informational).
- No statistical significance test; the minimum scenario time is the only guard against noise.

## Decisions

### D1. Working map is derived from the original, never edited in place
`IgnitionMapState` keeps `original` (16x16), `offset` (int) and derives each affected cell as `max(0, min(ceiling, original + offset))`. Alternative considered: reuse `VeMapState`-style cumulative `adjust` with ±1; rejected because clamping at 0 loses information (a cell lowered to 0 would not return to its original value when the offset comes back up), which the user explicitly asked to avoid.

### D2. Offset applies to all columns of the rows at or below the MAP limit
Chosen by the user over a RPM-limited rectangle or an interpolation-weighted edit. Consequence: idle and low-RPM cells in those rows move too. Accepted by the user. The MAP axis comes from the same breakpoints as the VE map; the affected rows are computed from the axis, so a different axis needs no code change.

### D3. Ignition rows are loaded only while the offset is 0
`load_row` replaces the original only at offset 0. If rows are re-read from the ECU while an offset is applied (reconnect), they contain our own writes, not the original, so they are ignored. Alternative: always replace the original and reset the offset to 0; rejected because the displayed scenarios would then be compared against a polluted baseline and "R" would restore the wrong values.

### D4. Analysis is a pure object driven by `(signals, now)` calls
`IgnitionAnalysis` has no Qt and no clock: the caller passes a monotonic timestamp with every telemetry set and with every event (`offset_changed`, `write_finished`, `paused`, `resumed`, `reset`). Alternatives: reading `time.monotonic()` inside (needs patching in tests) or counting samples instead of seconds (frame rate is not guaranteed; time is what the user reasons about). It returns plain dataclasses (`ScenarioStats`) and a "scenario ready" flag/callback. Means are plain sample means, not time-weighted, because frames are periodic.

### D5. Settling is tracked by the analysis, started by the write
An offset change makes the analysis "awaiting write" (all sets discarded). `RowWriteController` calls back after its timer expires (whether or not rows were sent, since an undone edit sends nothing but must still release the analysis); the analysis then waits `settle_seconds`. Alternative: confirm by watching the live `IGN` value change by the offset; rejected as fragile (IGN depends on the operating point and the cell weights). The `IGN` mean shown in each column remains a human-readable proof that the write took effect. The same settle time also follows a resume and the lambda loop closing again after being open (the ECU is still converging then, and the injection time would be skewed); the analysis watches `LAMBDA_LOOP` on every set, even those it discards for other reasons, so an open-loop excursion outside the band is not missed.

### D6. Knock is a count of increases inside valid runs
The ECU counter is cumulative until power-off, so the per-scenario value is the sum of positive steps between consecutive samples of a contiguous run (gap ≤ 1 s). A decrease is a counter restart and adds nothing. This keeps knock from driving elsewhere out of the numbers.

### D7. Generalize the row write controller
Extract `RowWriteController` (debounce timer, ascending row loop, mark-sent-before-send, sound, optional "write finished" hook) parameterized by callables (pending rows, row values, mark sent, command for row). `VeWriteController` keeps its public name and constructor and delegates to it, so the VE behavior and its tests are unchanged. Alternative: copy the class for ignition; rejected to avoid two diverging write paths for the same hardware protocol.

### D8. Module layout and wiring
```
app/ui/ignition_tuning/
  ignition_map_state.py   IgnitionMapState + module singleton ignition_map_state
  analysis.py             IgnitionAnalysis, ScenarioStats
  screen.py               IgnitionTuningScreen (view, keys, sounds, 100 ms refresh)
app/ui/common/row_write_controller.py   (shared by VE and ignition)
```
`AppWindow` registers the screen, connects `signal_processor.emitter` to `on_signal_received` (ignored unless the screen is active), adds `ignition_tuning` to the data-screens that announce keys, and Home gets a third entry. The screen subscribes to `vehicle_state.emitter` in its constructor (like the VE screen) so ignition rows and MAP breakpoints loaded during the handshake, before the user opens the screen, still reach the model. `ignition_map_state` is a module singleton like `ve_map_state` and is reset in the test fixture that uses it.

### D9. Protocol and catalog additions
`EcuCommand`/`EcuResponse` gain `IGN_ROW_1..16` (`#I01..#I16`). `_fetch_ve_map` is mirrored by `_fetch_ignition_map`, run after the VE rows and before streaming starts. The mock publishes a fixed ignition map. `INJ_PULSE` (position 7, raw/100 ms) is inferred from the sample log (107 at 6 % duty and about 3400 RPM is about 1.07 ms for a once-per-revolution injection); the real unit must be checked on the car.

### D10. View
One `QFrame` per scenario inside a horizontal layout, rebuilt only when the number of scenarios changes and otherwise updated in place every 100 ms. The best column gets a thick colored border; the current-offset column gets a distinct header color. Fonts are large (the driver glances). Status text priority is a pure function of (paused, loaded, settling, in-range) so it can be tested without rendering.

### D11. Leaving the screen keeps the state
ESC does not restore the original map. The state stays in memory and in the ECU RAM so the driver can leave and come back. Alternative: restore on exit; rejected for now because the user wants "R" as the only reset and may want to read the result after pulling over. See Risks.

## Risks / Trade-offs

- [The driver leaves the screen or the app with an offset still written] → Home does not show it; writes are RAM-only, so a power cycle restores the stored map. A visible offset indicator on Home or an exit-time restore can be added later.
- [The car is power-cycled while the app keeps running with an offset] → the app believes the ECU holds the offset while it holds the original; the `IGN` mean per column shows the discrepancy and R (rewrites all 16 rows) or any Up/Down fixes it.
- [1 degree changes MAP, pedal and injection time by less than the noise] → minimum analysed time per scenario, percentages only between eligible scenarios and no "best" until two are eligible; no confidence interval is shown.
- [Injection time is only comparable at the same lambda] → samples require closed loop (1 or 2); the mean lambda of each column is shown; the user judges equality.
- [Idle and low RPM move with the offset (option B)] → accepted by the user; "R" restores the original.
- [`INJ_PULSE` unit and the knock counter semantics are inferred] → manual verification task on the real ECU.
- [Reload of rows ignored while offset ≠ 0 hides a change made in the ECU by another tool] → acceptable for an on-road session; reset (R) at offset 0 re-reads nothing, so restart the connection to reload.

## Migration Plan

No data migration. Add an `ignition_tuning` section to `config.json` (all keys optional; defaults apply otherwise). Rollback is reverting the change; nothing is persisted in the ECU.

## Open Questions

- Which sound files to use for write, ready, pause and resume cues (functional with the existing files; the user can swap them in `config.json`).
