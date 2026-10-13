## 1. Wiring

- [x] 1.1 Add a slot on `AppWindow` that forwards the alarm onset signal to the Dashboard, connect `alarm_processor.emitter` to it in `main.py`, and verify the connection is made at startup
- [x] 1.2 Remove the obsolete TODO comment for this wiring from `main.py`

## 2. Color rule

- [x] 2.1 Update `update_display` in `app/ui/dashboard/screen.py` so any signal outside its limits is red regardless of `enabled`, with the flash guard intact, and verify with the mock that an alarm-enabled signal above its limit turns red (CLT was used: RPM is red by default)
- [x] 2.2 Verify with the mock (or by temporarily lowering a limit locally) that the card alternates black and yellow every 200 ms while the alarm is firing and returns to black afterwards
- [x] 2.3 Verify a signal with its alarm disabled (for example BOOST) turns red without flashing

## 3. Documentation and verification

- [x] 3.1 Remove the "pending full wiring" remark from the README (already gone) and document the flash and the red value
- [x] 3.2 Run `openspec validate wire-alarm-flash --strict` and verify it passes

## 4. Unit tests

- [x] 4.1 Extend `tests/test_dashboard.py` (timers driven manually): the card alternates black/yellow every 200 ms with red text while firing, returns to black when it stops, and a signal without a card is ignored; an alarm-enabled signal above its limit is red
- [x] 4.2 Extend `tests/test_window.py`: the alarm onset slot reaches the Dashboard
- [x] 4.3 Run the full suite (`python -m pytest`) and verify it passes
