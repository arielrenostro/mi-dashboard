## 1. Error reporting

- [ ] 1.1 Add an error signal to the thread wrapper and make the connection able to emit through it (no-op for the mock), and verify the mock still runs without errors
- [ ] 1.2 Report messages from the three failure paths in `serial.py` with the dedupe rule and reset on CONNECTED, and verify with an unavailable port that exactly one message is emitted across several retries
- [ ] 1.3 Pace failed connection attempts at 1 second with a wait that ends when the source stops, and verify CPU use is low while the port is missing and the app still exits promptly

## 2. Overlay

- [ ] 2.1 Create the overlay widget (square, centered, title plus wrapped message, transparent for mouse, no focus, 2 second timer) and show it from the window, then verify it appears on Home, Dashboard and VE screens
- [ ] 2.2 Connect the error signal to the overlay in `main.py`, then verify with a missing port that the overlay shows once, closes after 2 seconds, and that arrow keys and ESC still work while it is visible
- [ ] 2.3 Verify a second, different error replaces the message and restarts the 2 seconds

## 3. Documentation and verification

- [ ] 3.1 Run `openspec validate connection-error-overlay --strict` and verify it passes

## 4. Unit tests

- [ ] 4.1 Extend `tests/test_ecu_connection_serial.py`: an error is reported for a failed open, an I/O error and three empty reads; an identical message is reported once; reporting re-arms after CONNECTED; failed attempts wait 1 s (patched sleep) and stop waiting when the source stops; the mock never reports
- [ ] 4.2 Create `tests/test_error_overlay.py`: the overlay is square and centered, shows the message, hides after 2 s (timer), a second message replaces the text and restarts the timer, and it neither takes focus nor consumes key events
- [ ] 4.3 Extend `tests/test_window.py`: the error signal shows the overlay on every screen and keys are still routed to the active screen while it is visible
- [ ] 4.4 Run the full suite (`python -m pytest`) and verify it passes
