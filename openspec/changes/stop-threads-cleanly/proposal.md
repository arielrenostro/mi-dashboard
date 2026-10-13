## Why

Closing the app aborts the process with "QThread: Destroyed while thread is still running" (known issue K15): `main()` asks the ECU and alarm threads to stop but never waits for them, and the datalog thread is never stopped at all. Rows still queued for the CSV can be lost and the log file is never closed. While investigating, a second defect appeared (K18): `EcuConnectionSerial.stop()` only closes the port and does not clear its running flag, so a connect loop that keeps retrying (port unavailable) never ends and the ECU thread can never finish.

## What Changes

- Each thread owner stops and waits for its own thread, with a bounded wait: ECU source (3 s), alarm (1 s), datalog (3 s).
- The serial source's `stop()` also clears the running flag, ending connect and handshake loops.
- The datalog gets a `close()` that writes every queued row, closes the file and ends its thread; it is idempotent.
- A small shutdown routine runs the steps in a fixed order (window, ECU source, alarm, datalog) and isolates failures, called from `main()` in a `finally` block.
- No user-visible feature changes.

## Capabilities

### New Capabilities

- `app-lifecycle`: orderly, bounded and failure-tolerant shutdown of the whole app.

### Modified Capabilities

- `ecu-connection`: "Shutdown" also finishes the thread and ends retry loops.
- `alarms`: adds "Clean shutdown of the alarm".
- `datalog`: adds "Clean shutdown of the log".

## Impact

- `app/ecu_connection/serial.py`, `app/ecu_connection/thread.py`, `app/alarm/processor.py`, `app/log_writer/log_writer.py`, a new `app/lifecycle.py`, and `main.py` (shutdown section).
- Resolves K15 and K18 of the archived baseline design.
- Touches the same lines of `main.py` as `wire-alarm-flash` and `remove-dormant-lambda-loop-code`; the conflicts are trivial.
