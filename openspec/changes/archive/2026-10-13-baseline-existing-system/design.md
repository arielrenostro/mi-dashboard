## Context

See `proposal.md` for the motivation. This document records how the system is put together **today** (derived from the code, not from `.specs/`), the policy used to write the baseline specs, the defects found while doing so, and the follow-up changes that came out of the migration review.

### Runtime wiring as built (`main.py`)

```
 ECU thread (serial or mock)
     |  line (str)
     +--> SignalProcessor ----------------------------+
     |        parsed set (dict)                       |
     |          +--> AlarmProcessor.process_signals   |  (limits, firing window)
     |          +--> VehicleState.update              |  (shared snapshot)
     |          +--> DashboardScreen.on_signal_received (grid + graph buffers)
     |                                                |
     +--> LogWriter.write (CSV, own thread)           |
                                                      |
 AlarmProcessor thread: polls VehicleState every 100 ms --> sound play/stop

 VeCalibrationScreen: 100 ms timer reads VehicleState (RPM, MAP, VE, ...)
     |  ve_adjustment_made --> VeWriteController (1 s debounce)
     |                              +--> EcuConnection.send_command(#F0N, 16 values)
     |  O / P --> EcuConnection.send_command(#D06 / #D05)
 VehicleState events (breakpoints, VE row) --> VeCalibrationScreen --> VeMapState

 AppWindow --> keyPressEvent/keyReleaseEvent --> current screen only
```

### Threads

| Thread | Work |
|---|---|
| Main (Qt) | UI, signal/slot dispatch, all media players |
| ECU source | blocking serial I/O or mock replay, command queue drain |
| Alarm poller | 100 ms loop that asks the UI thread to play or stop the alarm sound |
| Log writer | CSV disk writes |

Cross-thread communication uses Qt signals. The shared `VehicleState` is protected by a re-entrant lock. Commands are queued through a thread-safe queue and written by the ECU thread.

### Startup and shutdown order

1. Logging configured; Qt application created.
2. Log writer opens the per-run CSV; alarm processor starts.
3. Signal processor created and connected to alarms and shared state.
4. ECU source (serial or mock) created and registered.
5. Window created (registers Home, Dashboard, VE calibration; Dashboard connected to the signal processor) and shown full-screen on Home.
6. ECU source connected to the signal processor and the log writer; ECU thread started.
7. On exit: window closed, alarm processor stopped, ECU source stopped.

## Goals / Non-Goals

**Goals:**
- Give the project a verified, code-derived OpenSpec baseline of 13 capabilities.
- Record every divergence between documentation, intent and code so each can be handled deliberately.

**Non-Goals:**
- Changing any application code, configuration or the legacy documents.
- Specifying features that are not wired (event marker, alarm flash, Space-hold lambda toggle, lambda loop state filter).
- Fixing the defects listed below.

## Decisions

### D1. Baseline describes current behavior
The code was declared the source of truth. Where code and documents disagree, the specs follow the code. Alternative considered: write intended behavior and open tasks to match; rejected because the baseline could no longer be checked against the running system.

### D2. Defects are not enshrined
Where the code has a clear defect, the spec states the behavior without the defect (or points to Known issues) and the defect is listed below. Exception: where the user confirmed the behavior as intentional (red value for limit-exceeded signals with a disabled alarm; reset rewrites all 16 rows), it is a requirement.

### D3. Capability partition
Capabilities follow domains, not input devices: there is no `keyboard-actions` capability because every key belongs to the screen that owns it (`screen-navigation`, `dashboard`, `ve-calibration-screen`, `lambda-loop-control`). The legacy `data_pipeline` document is replaced by the wiring diagram above. `app-configuration` is new (no legacy document).

### D4. Dormant code is outside the baseline
Components that exist but are not instantiated or connected are not specified. They become requirements only when a follow-up change wires them.

### D5. Language
Specs are written in English, consistent with the repository documents and OpenSpec keywords.

### Documentation vs code: review outcome

| Topic | Legacy documents said | Decision |
|---|---|---|
| VE write command | one `#D04` after debounce | Keep code: row-by-row `#F0N`, no `#D04` |
| VE unit and step | float %, +/-6 (or 5) | Keep code: raw ints, +/-5 raw (0.5 % VE) |
| Lambda loop keys | Space hold (2 s) | Keep code: O / P on VE screen. The displayed loop state follows ECU telemetry, and the ECU answers the command with feedback, so the keys do not need to update any state (no follow-up) |
| Connect sequence | `#D50` then `#D01` | Keep code (breakpoints and VE rows in between) |
| VE table layout | 16x17 with label column, heatmap image | Keep code: 16x16 table, line graph |
| Modified cell color | pending cells, 0.05 tolerance | Keep code: any difference from original |
| Datalog | fixed `LOG_FILE`, append | Keep code: per-run timestamped file in `datalog.path` |
| CSV column indices | shifted by 2 after `Mess 2` | Keep code (documents were wrong) |
| Window title | "Master Injection Dashboard" | Documents win (follow-up) |
| `VE_LAMBDA` signal | undocumented | Keep code |
| ESC on Home | exit (README) | Should exit (follow-up) |
| Red for disabled-alarm limits | red outside range | Confirmed intentional |
| Reset | restore only | Confirmed: also rewrites all 16 rows |
| Mock pacing | by log timestamps | Should be configurable skip (follow-up); current pacing is fixed 0.1 s |
| Lambda loop value 2 | undocumented | `0` open, `1` closed, `2` closed with automatic correction |
| `ERROR` connection status | red "Error" | Baseline reflects what is observable today; errors will be shown as a 2 s square overlay (follow-up `connection-error-overlay`) |

## Known issues (not part of the specs)

| # | Issue | Evidence | Planned handling |
|---|---|---|---|
| K1 | VE row 16 (`#F16`) is never requested from the ECU; the highest-MAP row stays at zero on real hardware (the mock loads all 16) | `ecu_connection/serial.py` `_fetch_ve_map` loops `range(1, 16)` | `fetch-ve-row-16` |
| K2 | Signals with the alarm **enabled** (RPM, MAP, INJ_UTIL, CLT, VSS, FUEL_TRIM) never turn red on the grid, because the grid skips recoloring when an alarm is enabled and the flash that should do it is not connected. Signals with the alarm disabled but limits defined (BOOST, LAMBDA, IGN, IAT, LAMBDA_TARGET) do turn red | `dashboard/screen.py` `update_display` | Resolve inside `wire-alarm-flash` |
| K3 | Lambda loop value `2` (closed + automatic correction) is shown as `Open` and colored orange; only the VE lambda dot treats `2` as closed | `signal.py` LAMBDA_LOOP `for_label`; `ve_calibration/screen.py` `_update_top_bar` | `lambda-loop-closed-corr-display` |
| K4 | A VE row received from the ECU (including after a reconnect) overwrites unsent user edits, although the docstring says edits are preserved | `ve_map_state.py` `load_row` | Decide in a later change |
| K5 | Modified-cell highlight skips the first RPM column | `ve_calibration/screen.py` `mark_modified_cells` iterates columns 1..15 | Later change |
| K6 | Edits are rounded per cell; a cell with interpolation weight below 0.1 never changes with +/-5 | `ve_map_state.py` `adjust_ve` / `set_cell` | Later change |
| K7 | `datalog.path` defaults to the OS path-list separator, not a directory; without a `datalog` section the log cannot be opened | `config.py` | Later change |
| K8 | Needs Python 3.12 or newer (nested quotes inside an f-string in `main.py`); the README says 3.9+ | `main.py` | Later change (code or README) |
| K9 | VE row index validation is always false (`0 > idx > 15`) | `state/state.py` `set_ve_map` | Later change |
| K10 | `ERROR` status is replaced by `DISCONNECTED` immediately, so it is never visible | `serial.py` `run` / `_close` | `connection-error-overlay` |
| K11 | The ECU thread start sets its running flag after the thread has started; the loop could exit immediately | `ecu_connection/thread.py` | Later change |
| K12 | The mock skips the first 12249 lines (debug offset) and has a dead branch (format check for 33 separators, timestamp pacing) so the app's own CSV logs cannot be replayed | `ecu_connection/mock_log.py` | `mock-skip-lines-config` |
| K13 | ESC on Home does nothing (the close callback is passed but never used) | `ui/home/screen.py` | `home-esc-closes-app` |
| K14 | No window title is set | `ui/window.py` | `window-title` |
| K15 | Threads (ECU, alarm, log) are stopped without waiting for them to finish | `main.py` | Later change |
| K16 | `ve_calibration/screen.py` keeps unused code (`populate_ve_table`, an unused write-controller signal); the commented block in `main.py` references `EcuCommand.ve_row`, which does not exist | various | `remove-dormant-lambda-loop-code` |
| K17 | When the port cannot be opened the connect loop retries with no delay, so it spins and logs a warning on every iteration | `serial.py` `connect` (`while self.running` with no sleep or backoff) | Handle in `connection-error-overlay` (error reporting must not fire per iteration) |

### Dormant code (exists, not wired)

`EventMarker`, `KeyHoldDetector`, `LambdaToggle`, `LambdaLoopStateProcessor`, `StateProcessorRegister`, the shared lambda-loop flag in `VehicleState`, and the dashboard's alarm flash handler. The window has no key-event signals for them. `StateProcessorRegister` connects the ECU line signal (text) to a slot expecting a command and arguments; that mismatch would have to be resolved before wiring it.

Only `EventMarker` and the alarm flash handler have a planned wiring change. The lambda-loop pieces (`LambdaToggle`, `KeyHoldDetector` for Space, `LambdaLoopStateProcessor`, `StateProcessorRegister`, the flag) have no consumer in the agreed design, since the loop state shown comes from ECU telemetry; they are to be removed by `remove-dormant-lambda-loop-code`.

## Follow-up changes (outside this baseline)

| Change | Intent |
|---|---|
| `wire-event-marker` | Enter plays a sound and marks the next CSV row with `MARK` |
| `wire-alarm-flash` | Connect the alarm onset notification to the grid flash; resolve K2 |
| `home-esc-closes-app` | ESC on Home exits the app (K13) |
| `window-title` | Set the title to "Master Injection Dashboard" (K14) |
| `mock-skip-lines-config` | Make the number of skipped mock lines a configuration key, default none (K12) |
| `fetch-ve-row-16` | Request all 16 VE rows (K1) |
| `lambda-loop-closed-corr-display` | Show value `2` as closed, with the right color (K3) |
| `connection-error-overlay` | A square, dialog-like overlay shows a connection error for 2 seconds and then closes; a repeated identical error is not reopened (K10, K17) |
| `remove-dormant-lambda-loop-code` | Delete the unused lambda-loop components and the unused code listed in K16 |

Dropped during review: `lambda-loop-keys-update-state` (the ECU already returns the loop state after O / P, and the UI follows telemetry).

## Risks / Trade-offs

- [Specs encode accidental behavior] → Defects are excluded (D2) and the few intentional quirks are marked as confirmed.
- [Baseline drifts from code during follow-ups] → Each follow-up modifies the relevant capability through a delta.
- [Legacy documents contradict the new specs] → Decided: delete `.specs/` and `ARCHITECTURE.md` after the baseline is archived (they stay recoverable from git history); until then they are stale.

## Resolved during review

- Connection errors are surfaced as a square, dialog-like overlay shown for 2 seconds and then closed (follow-up `connection-error-overlay`).
- The lambda loop state shown comes from ECU telemetry, which the ECU updates after an open/close command; keys do not update state.
- Legacy documents: delete `.specs/` and `ARCHITECTURE.md` after archive.

- Overlay with a repeated error (K17): show it once per new error. If the message equals the last one shown, do not reopen it until a different message appears or the connection is re-established.
- `README.md` and `CLAUDE.md` keep installation, running, the configuration table, features, screens and shortcuts. They lose the protocol, the ECU field table, the CSV format, the architecture diagrams and the "Pending features" list (covered by the specs). `CLAUDE.md` keeps a short paragraph pointing to `openspec/specs/`.
- The lambda-loop pieces without a consumer (`LambdaToggle`, Space `KeyHoldDetector` use, `LambdaLoopStateProcessor`, `StateProcessorRegister`, the flag in `VehicleState`) are to be removed in a cleanup change. `KeyHoldDetector` itself is removed only if nothing else uses it when that change is made.

## Open Questions

None blocking the baseline.
