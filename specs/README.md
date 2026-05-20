# Specs — MI Dashboard

This directory contains the Spec Driven Development (SDD) specifications for the MI Dashboard project.

## What is SDD?

Spec Driven Development is a practice where **formal specifications are written before (or alongside) code**. Specs are the source of truth for what the system should do. They are structured enough for an AI agent to read and produce correct implementations, and human-readable enough to reason about design decisions.

The key principle: **if the spec changes, the code changes — not the other way around**.

## How specs are structured here

Each spec file describes one concern of the system. Files use consistent formats:

- **Tables** for enumerable definitions (signals, commands, columns)
- **Code blocks** for formulas, frame formats, and data examples
- **Field lists** for configuration and behavior rules
- **`Intent:` notes** for non-obvious design decisions that must be preserved

## How to use these specs

### Implementing a feature from scratch

1. Read the relevant spec file(s)
2. Use the spec as the instruction set — field names, formulas, and rules are authoritative
3. Do not invent behavior not described in the spec
4. If behavior is ambiguous, ask before guessing

### Modifying existing behavior

1. Update the spec first
2. Then update the code to match
3. Never update code and leave the spec stale

### Adding a new signal

1. Add a row to `signals.md` (direct signals table or calculated signals table)
2. Add the signal to the layout in `dashboard_layout.md`
3. Update the code: `Signal` enum in `app/master/signal.py`, layout in `app/dashboard/grid.py`

### Adding a keyboard action

1. Add a row to `keyboard_actions.md`
2. Implement in `app/event/` and wire in `main.py`

## File index

| File | Describes |
|---|---|
| `signals.md` | All ECU telemetry signals — indices, converters, display, alarms |
| `ecu_protocol.md` | Serial protocol, frame format, commands, handshake, reconnect |
| `dashboard_layout.md` | Grid and graph layout, refresh rate, display rules |
| `keyboard_actions.md` | All keyboard-triggered actions and their behavior |
| `alarm_system.md` | Alarm thresholds, audio behavior, visual flash pattern |
| `data_pipeline.md` | Data flow, threading model, component wiring |
| `logging.md` | CSV format, column definitions, event marking |
