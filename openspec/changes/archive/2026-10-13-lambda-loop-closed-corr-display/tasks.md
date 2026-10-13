## 1. Display

- [x] 1.1 Change the `LAMBDA_LOOP` label in `app/masterinjection/signal.py` to return `Closed`, `Closed+C` or `Open`, and verify the three values `1`, `2`, `0` produce those strings
- [x] 1.2 Make the VE top bar color green for raw values 1 and 2 in `app/ui/ve_calibration/screen.py`, and verify with the mock (or a stub value) that 2 shows green and the text fits the card

## 2. Verification

- [x] 2.1 Run `openspec validate lambda-loop-closed-corr-display --strict` and verify it passes

## 3. Unit tests

- [x] 3.1 Extend `tests/test_signal_model.py`: LAMBDA_LOOP display is `Open` for 0, `Closed` for 1 and `Closed+C` for 2
- [x] 3.2 Extend `tests/test_ve_calibration_screen.py`: the top bar card is green and reads `Closed+C` for value 2, and orange for 0
- [x] 3.3 Run the full suite (`python -m pytest`) and verify it passes
