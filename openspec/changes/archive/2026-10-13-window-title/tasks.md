## 1. Implement

- [x] 1.1 Call `setWindowTitle("Master Injection Dashboard")` in `AppWindow` and verify the title appears in the OS task switcher while the app runs
- [x] 1.2 Run `openspec validate window-title --strict` and verify it passes

## 2. Unit tests

- [x] 2.1 Add a test to `tests/test_window.py` asserting `windowTitle()` is `Master Injection Dashboard`, and verify it fails before the change and passes after
- [x] 2.2 Run the full suite (`python -m pytest`) and verify it passes
