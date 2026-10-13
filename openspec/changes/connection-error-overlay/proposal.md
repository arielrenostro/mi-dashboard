## Why

Connection errors reach the user only through the log: the `ERROR` status is overwritten by `DISCONNECTED` immediately (K10), and when the port cannot be opened the connect loop retries without any delay and logs on every pass (K17). The user wants the error shown on screen. See the archived `baseline-existing-system` change (design.md, Known issues) for the full context.

## What Changes

- A square, dialog-like overlay shows the connection error for 2 seconds on whatever screen is active, then closes by itself.
- The serial source reports an error message for open failures, I/O errors and silent-link reconnects, and does not repeat an identical message until a different one appears or the connection recovers.
- Failed connection attempts are paced at one per second.

## Capabilities

### New Capabilities

### Modified Capabilities

- `ecu-connection`: adds "Connection error reporting" and "Connect retry pacing".
- `screen-navigation`: adds "Connection error overlay".

## Impact

- `app/ecu_connection/ecu_connection.py`, `serial.py`, `thread.py`, `app/ui/window.py`, a new overlay widget in `app/ui/components/`, `main.py` (connect the signal).
