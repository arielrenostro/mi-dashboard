## Context

`EventMarker` filters Return/Enter, plays a sound and emits a signal; `LogWriter` already has a method that sets a one-shot pending flag consumed by the next written row. Neither is connected. The window forwards key events only to the active screen and has no key signal.

## Goals / Non-Goals

**Goals:** wire marker, log writer and key events; make the sound configurable.

**Non-Goals:** other marker types, a marker UI, or marking in the mock log beyond what already happens.

## Decisions

- **Scope of the key:** active on the Dashboard and the VE screen only. The original documentation called it global, but on Home Enter already opens a screen and a mark there would be noise in the log. Recorded here as an assumption; changing to global is a one-line condition.
- **Mechanism:** the window emits a key signal for non-repeating presses while a data screen is active; the marker is connected to it. Alternative: let each screen call the marker; rejected as duplicated code in two screens.
- **Auto-repeat:** filtered where the signal is emitted, so holding the key marks once.
- **Flag, not counter:** reuse the existing one-shot flag; multiple presses before a frame yield one mark.
- **Sound setting under `datalog`:** it belongs to the log marking feature.

## Risks / Trade-offs

- [Beep and `MARK` fire even if no frames are arriving] -> the mark applies to the next frame whenever it comes; acceptable.
- [Marker created in the main thread, log writer receives frames queued from the ECU thread] -> both live in the main thread, so the flag has no race.
