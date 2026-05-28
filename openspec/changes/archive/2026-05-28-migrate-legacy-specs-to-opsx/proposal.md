## Why

The project already has 10 specification files under `.specs/` written in an SDD (Spec Driven Development) style. These specs are not tracked in the OpenSpec model, making them invisible to OPSX workflows (apply, propose, archive). Migrating them makes the existing design knowledge first-class citizens in the OPSX toolchain.

## What Changes

- Each `.specs/*.md` file becomes a spec at `openspec/specs/<kebab-name>/spec.md`, preserving all content and structure.
- The `.specs/` directory and its `README.md` are kept as-is for backwards compatibility (they can be removed in a follow-up).
- No code changes — this is a documentation/metadata migration only.

## Capabilities

### New Capabilities

- `signals`: All ECU telemetry signals — indices, converters, display, alarm config
- `ecu-protocol`: Serial protocol, frame format, commands, handshake, reconnect logic
- `dashboard-layout`: Grid and graph layout, refresh rate, display rules
- `keyboard-actions`: All keyboard-triggered actions and their behavior
- `alarm-system`: Alarm thresholds, audio behavior, visual flash pattern
- `data-pipeline`: Data flow, threading model, component wiring
- `logging`: CSV format, column definitions, event marking
- `screen-navigation`: Multi-screen architecture, AppWindow, Screen base class, navigation rules
- `ve-map-model`: VE map data model, axis definitions, bilinear interpolation, edit API
- `ve-calibration-screen`: VE calibration screen layout, live highlighting, keyboard editing
- `ve-write`: Deferred VE map write to ECU — debounce, command dispatch, audio feedback

### Modified Capabilities

## Impact

- `openspec/specs/` gains 11 new spec directories, each with a `spec.md`.
- No production code is touched.
- Existing `openspec/specs/ve-percentage-increment/` is unaffected.
