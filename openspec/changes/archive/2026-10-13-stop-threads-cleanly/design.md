## Context

On exit `main()` runs `app_window.close()`, `alarm_processor.stop()` and `get_ecu_connection_thread().stop()`. `AlarmProcessor.stop()` only clears a flag, `EcuConnectionThread.stop()` stops the connection and clears its own flag, and `LogWriter` has no shutdown at all. None of them waits. When `main()` returns, the local variables are destroyed and Qt aborts on the `QThread` objects that are still running. `EcuConnectionSerial.stop()` overrides the base class and closes the port without clearing `running`, which the connect loop (`while self.running`) depends on. `main.py` cannot be imported on Python 3.10 (known issue K8), so anything that must be tested lives outside it.

## Goals / Non-Goals

**Goals:** the process exits with status 0 and no Qt error; queued log rows are not lost; a stuck component cannot hang or crash the exit.

**Non-Goals:** changing what is logged, reconnect behavior, or the connection error reporting of `connection-error-overlay`.

## Decisions

- **Each owner waits for its own thread.** `EcuConnectionThread.stop(timeout_ms=3000)`, `AlarmProcessor.stop()` (1 s) and a new `LogWriter.close()` (3 s). Alternative: wait in `main()`; rejected because the owners know their thread and tests can then cover them directly.
- **`EcuConnectionSerial.stop()` calls the base `stop()` first**, then closes the port. This ends `connect()` and `_send_and_retry()` loops.
- **Flush the log through the writer thread, with a bounded wait.** `LogWriter.close()` emits a `close_requested` signal that is queued behind the rows already queued; the worker flushes and closes the file, emits its existing `finished` signal, and that signal (connected directly) quits the thread. `close()` then waits for the thread with a limit. Alternatives: only `quit()` and `wait()`, rejected because it does not guarantee that queued rows are processed; a blocking queued call into the worker, rejected because it would block the main thread with no limit if the disk stalls. The `quit` connection must be direct: a queued call to the `QThread` object would need an event loop in the main thread, which no longer runs during shutdown.
- **Order: window, ECU source, alarm, datalog.** Stopping the ECU source first means no new frames arrive; the datalog goes last so it writes everything that did arrive.
- **A `shutdown()` routine in `app/lifecycle.py`** takes the four components, runs the steps in order and wraps each in its own try/except. It is called from a `finally` block in `main()`. Living outside `main.py` makes order and failure isolation unit-testable on Python 3.10.
- **On timeout, log a warning and call `terminate()`** on the stuck thread so the destructor does not abort. The process is exiting anyway. Alternative: leave the thread and call `os._exit`; rejected as harsher and untestable.
- **End-to-end check by subprocess:** one test starts real components in a child process, runs the shutdown routine and asserts exit code 0 and no "QThread: Destroyed" in stderr. The child is built like `main()` (everything inside a function, receivers connected as QObject slots) because the abort only happens when those objects are destroyed on return; with the shutdown disabled it dies with SIGABRT.

## Risks / Trade-offs

- [`terminate()` while a thread blocks in a serial read] -> only reached after the bounded wait, during exit.
- [The datalog wait delays exit by up to 3 s in the worst case] -> normally immediate, because the queue is short.
- [Conflicts in `main.py` with the other open changes] -> small and mechanical; apply this change before `remove-dormant-lambda-loop-code`.
