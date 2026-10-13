## Context

The ECU source runs on its own thread and already pushes lines through a Qt signal owned by the thread wrapper. The window is a single full-screen widget holding a stacked widget; keyboard events are handled by the window and forwarded to the active screen.

## Goals / Non-Goals

**Goals:** make connection errors visible without the log, without flooding the user; stop the spin in the connect loop.

**Non-Goals:** a persistent error log in the UI; surfacing errors from components other than the serial connection; changing the status values or Home status label.

## Decisions

- **Reporting path:** add a second Qt signal for error text next to the line signal on the thread wrapper, and give the connection a reference to it, mirroring the existing mechanism. The serial source calls a small helper that applies the dedupe rule and emits. The window shows the overlay from that signal (queued to the UI thread).
- **Implementation notes:** the dedupe lives in the `EcuConnection` base class (`report_error` / `clear_reported_error`), so any source gets it and the mock simply never calls it. The retry wait is a `threading.Event` that `stop()` sets, so shutdown interrupts it at once. Messages are capped at 240 characters before they are shown.
- **Dedupe policy (agreed during the baseline review):** an identical message is reported once; the memory resets when a different message arrives or the status reaches CONNECTED. Alternatives rejected: replace-and-restart on every error (overlay would stay up as long as the error lasts); fixed rate limit (arbitrary).
- **Overlay:** a child widget of the window, fixed square size, centered, raised above the stack, transparent for mouse events and without focus so key handling is unchanged. A single-shot 2000 ms timer hides it and is restarted on a new message.
- **Retry pacing:** wait 1 second after a failed attempt using a wait that ends early when the source stops, so shutdown is not delayed. This pacing was not explicitly requested during the review and is included because the dedupe alone would leave the CPU spin (K17); remove it from the spec and tasks if undesired.
- **Message language:** Portuguese UI text consistent with the existing menu labels; the underlying exception text is appended as is.

## Risks / Trade-offs

- [Error text may be long] -> wrap the text and cap the overlay size.
- [Mock source never reports errors] -> intended; there is no link to fail.
- [Suppressed repeats hide a persistent failure after the first 2 seconds] -> the Home status still shows `Disconnected`, and the log keeps the full history.
