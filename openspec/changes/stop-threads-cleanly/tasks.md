## 1. Component shutdown

- [ ] 1.1 Make `EcuConnectionSerial.stop()` clear the running flag (call the base `stop()`) before closing the port, and verify a connect loop on an unavailable port ends within 1 s of `stop()`
- [ ] 1.2 Make `EcuConnectionThread.stop(timeout_ms=3000)` stop the connection, then wait for the thread; on timeout log a warning and terminate it. Verify with a fake blocking connection that `stop()` returns and the thread is no longer running
- [ ] 1.3 Make `AlarmProcessor.stop()` stop the sound, clear the flag and wait up to 1 s, and verify the thread is no longer running afterwards
- [ ] 1.4 Add `Worker.close()` and `LogWriter.close()` (blocking flush through the writer thread, close the file, quit and wait up to 3 s; idempotent), and verify queued rows are all in the file afterwards

## 2. Orderly shutdown

- [ ] 2.1 Create `app/lifecycle.py` with `shutdown(window, ecu_thread, alarm, log_writer)`: close the window, stop the ECU source, stop the alarm, close the datalog, each step isolated by its own error handling, and verify the order with fakes
- [ ] 2.2 Call it from a `finally` block in `main()` in place of the three stop calls, and verify by reading the code that nothing else stops threads
- [ ] 2.3 Run the real `main()` with the mock source and with an unavailable serial port (offscreen, simulated close) and verify exit status 0 and no "QThread: Destroyed" message

## 3. Documentation and verification

- [ ] 3.1 Run `openspec validate stop-threads-cleanly --strict` and verify it passes
- [ ] 3.2 Manual check on Windows with the real ECU (not unit testable): close the app while streaming and while the ECU is off, and verify it exits without error messages and the CSV is complete

## 4. Unit tests

- [ ] 4.1 Create `tests/test_lifecycle.py`: steps run in the specified order; an error in one step is logged and the later steps still run; a missing component is tolerated
- [ ] 4.2 Extend `tests/test_ecu_connection_serial.py`: `stop()` clears the running flag and closes the port; a connect loop running in a thread ends after `stop()`; a request waiting for an ECU answer ends after `stop()`
- [ ] 4.3 Create `tests/test_ecu_connection_thread.py`: `stop()` waits until the thread has finished (fake and mock sources); a source that does not finish logs a warning and `stop()` still returns
- [ ] 4.4 Extend `tests/test_alarms.py`: start the real alarm thread, stop it, and verify it finishes and the sound is stopped
- [ ] 4.5 Extend `tests/test_datalog.py`: after `close()` every written row is in the file, the file is closed, the thread has finished, and a second `close()` is harmless
- [ ] 4.6 Create `tests/test_shutdown_process.py`: a child process starts the real components, runs `shutdown()` and exits with status 0 and no "QThread: Destroyed" in stderr
- [ ] 4.7 Run the full suite (`python -m pytest`) and verify it passes
