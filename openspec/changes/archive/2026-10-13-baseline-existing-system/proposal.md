## Why

The MI Dashboard project predates OpenSpec. Its behavior is described in `.specs/*.md`, `README.md`, `ARCHITECTURE.md` and `CLAUDE.md`, but those documents have drifted from the code (renamed paths, wiring documented as active that is commented out, different units and keys). The code is the real source of truth, so this change records what the system **actually does today** as the OpenSpec baseline. Future work then lands as explicit, reviewable changes against it.

## What Changes

- Create the initial OpenSpec capability specs, derived from the code (the `.specs/` documents were used only as a starting outline).
- The baseline describes **current behavior only**. Where the code has a clear defect, the defect is recorded in `design.md` under *Known issues*, not enshrined as a requirement.
- Features that are documented but not wired in `main.py` (event marker, alarm flash, Space-hold lambda toggle, lambda loop state filter) are **not** part of the baseline.
- No application code changes. `.specs/`, `README.md`, `ARCHITECTURE.md` and `CLAUDE.md` are left untouched; their fate is decided after this baseline is archived.

Follow-up changes already identified (out of scope here, listed in `design.md`): `wire-event-marker`, `wire-alarm-flash`, `home-esc-closes-app`, `window-title`, `mock-skip-lines-config`, `fetch-ve-row-16`, `lambda-loop-closed-corr-display`, `connection-error-overlay`, `remove-dormant-lambda-loop-code`.

## Capabilities

### New Capabilities

- `app-configuration`: `config.json` / `MI_DASHBOARD_CONFIG_FILE` loading, sections and defaults.
- `ecu-protocol`: frame format, command and response catalog of the Master Injection ECU serial protocol.
- `ecu-connection`: serial lifecycle (connect, sync, stream, reconnect), connection status, thread-safe command queue, mock replay.
- `signal-model`: the `Signal` catalog, converters, calculated signals, frame parsing into `ParsedSignal`.
- `vehicle-state`: shared thread-safe state (latest signals, alarm timestamps, lambda loop flag, breakpoints, VE map) and change events.
- `alarms`: limit evaluation, 2 s firing window, looping audio.
- `dashboard`: numeric grid and live graphs with peak/min markers.
- `screen-navigation`: full-screen window, screen lifecycle, key routing, Home screen and connection status.
- `ve-map-model`: in-memory 16x16 raw VE map, bilinear interpolation, edit and reset semantics.
- `ve-calibration-screen`: VE table, VE graph, top bar, keyboard editing.
- `ve-write`: debounced row-by-row write of modified VE rows to the ECU.
- `datalog`: per-run CSV log of raw frames.
- `lambda-loop-control`: manual open/close of the lambda loop from the VE calibration screen.

### Modified Capabilities

<!-- None: openspec/specs/ is empty. -->

## Impact

- Adds files only under `openspec/changes/baseline-existing-system/`. After archive, `openspec/specs/` is populated.
- No impact on code, dependencies, runtime behavior or `config.json`.
- Subsequent changes (see list above) use these specs as their base.
