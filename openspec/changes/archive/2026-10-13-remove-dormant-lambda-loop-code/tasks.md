## 1. Remove dormant lambda loop code

- [x] 1.1 Search for references to `LambdaToggle`, `KeyHoldDetector`, `LambdaLoopStateProcessor`, `StateProcessorRegister`, `Processor` and the lambda flag methods and verify the only references are in the files to be deleted or in comments
- [x] 1.2 Delete `app/event/lambda_toggle.py`, `app/event/key_hold_detector.py`, `app/state/processors/` and `app/state/register.py`
- [x] 1.3 Remove `_lambda_loop_closed`, `set_lambda_loop_state` and `is_lambda_loop_closed` from `app/state/state.py`

## 2. Remove other unused code

- [x] 2.1 Remove `populate_ve_table` from `app/ui/ve_calibration/screen.py` and the unused `command_requested` signal from the write controller, verifying nothing references them
- [x] 2.2 Remove the commented-out wiring block from `main.py`

## 3. Verification

- [x] 3.1 Run the app with the mock, open the Dashboard and the VE screen, press O and P, and verify no import errors and unchanged behavior
- [x] 3.2 Run `openspec validate remove-dormant-lambda-loop-code --strict` and verify it passes

## 4. Unit tests

- [x] 4.1 No behavior changes, so no new scenarios: verify the existing suite (in particular `tests/test_window.py`, which builds every screen, and `tests/test_vehicle_state.py`) passes unchanged
- [x] 4.2 Run the full suite (`python -m pytest`) and verify it passes
