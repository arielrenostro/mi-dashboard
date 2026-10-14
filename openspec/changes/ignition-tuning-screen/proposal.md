## Why

The ignition map is tuned today outside the car, with no objective feedback. The owner wants to find the best spark advance for light-load highway cruising on the road: hold a fixed RPM in a fixed gear, change the advance by 1 degree at a time, and see which setting needs the least fuel, MAP and pedal for the same speed. The driver cannot look at the screen while driving, so the screen must be driven by very few keys and give audible feedback.

## What Changes

- New **Ignition tuning** screen, opened from Home, that:
  - reads and writes the ECU ignition map (`#I01`..`#I16`, same row logic as the fuel `#F` rows);
  - applies one global advance **offset** (Up = +1 degree, Down = -1 degree) to every cell of the rows whose MAP breakpoint is at or below a configured limit (70 kPa), for all RPM columns; rows above the limit are never touched;
  - always computes the written map from the **original** ECU map (`max(0, min(50, original + offset))`), never cumulatively, so cells clamped at 0 return to their original value when the offset comes back up;
  - samples telemetry only while RPM is inside the configured band, the gear is the configured one, the lambda loop is closed (value 1 or 2), the analysis is not paused and the setting has settled;
  - shows one column per offset tried (ordered by degrees): RPM band, analysed time, offset, mean ignition, mean injection time, mean MAP, mean pedal, mean lambda and a knock counter delta;
  - shows, for injection time, MAP and pedal, the percentage difference to the best value of that sensor, and highlights with a border the scenario with the lowest mean injection time;
  - `Space` pauses and resumes the analysis (for hills), `X` discards the worst scenario (the highest mean injection time among comparable ones, never the one of the current offset), `R` restores the original map and clears the analysis, `Esc` returns to Home; audible cues confirm a write, a pause/resume, a discard and a scenario that has gathered enough time.
- New signals in the catalog: `INJ_PULSE` (injection pulse, frame position 7) and `KNOCK` (knock counter, position 11).
- New ECU commands/responses `#I01`..`#I16`; the serial handshake also loads the ignition map, and the mock source publishes a fixed one.
- Shared state holds the ignition map and emits a change event for each ignition row.
- New `ignition_tuning` configuration section (RPM band, gear, MAP limit, ceiling, timings, sounds).
- Enter keeps marking events in the datalog on the new screen.

## Capabilities

### New Capabilities
- `ignition-map-model`: the 16x16 ignition map as original + global offset, which rows the offset applies to, clamping, pending rows, reset.
- `ignition-analysis`: sample gating, per-offset accumulation (time, means, knock delta), percentage differences and best-scenario rule.
- `ignition-tuning-screen`: layout, keys, audible cues, pause, and the debounced row-by-row write of the ignition map.

### Modified Capabilities
- `ecu-protocol`: command and response catalog gain `#I01`..`#I16`; ignition row addressing.
- `ecu-connection`: connect sequence loads the 16 ignition rows; ignition row publication; mock publishes a fixed ignition map.
- `signal-model`: `INJ_PULSE` and `KNOCK` direct signals.
- `vehicle-state`: ignition map storage and its change event.
- `app-configuration`: `ignition_tuning.*` settings.
- `screen-navigation`: a fourth screen (`ignition_tuning`), Home menu entry, Esc returns to Home.
- `datalog`: Enter marks events on the new screen as well.

## Impact

- Code: `app/masterinjection/protocol.py`, `signal.py`; `app/state/state.py`, `event.py`; `app/ecu_connection/serial.py`, `mock_log.py`; `app/config.py`; `app/ui/window.py`, `app/ui/home/screen.py`; new `app/ui/ignition_tuning/` package (model, analysis, write controller, screen); `config.json` sample.
- Tests: new `tests/test_ignition_map_model.py`, `test_ignition_analysis.py`, `test_ignition_tuning_screen.py`; updates to the signal, protocol, connection, state, configuration, navigation and datalog tests.
- Safety: writes go to ECU RAM only (`#D04` is never sent), so a power cycle restores the stored map.
- Not verifiable without hardware: the real `#I01`..`#I16` answers, the unit of the raw ignition value and the meaning of the knock counter on the real ECU (manual verification task).
