## 1. Implement

- [ ] 1.1 Handle `Qt.Key.Key_Escape` in `HomeScreen.keyPressEvent` by calling the close callback, and verify by reading the code that auto-repeat events are still ignored
- [ ] 1.2 Run the app, press ESC on Home and verify the app exits; open the Dashboard, hold ESC until Home appears and verify the app does not exit
- [ ] 1.3 Run `openspec validate home-esc-closes-app --strict` and verify it passes

## 2. Unit tests

- [ ] 2.1 Add tests to `tests/test_screen_navigation.py`: ESC on Home calls the close callback; an auto-repeat ESC does not; the existing arrow and Enter tests still pass. Verify the new tests fail before the change and pass after
- [ ] 2.2 Run the full suite (`python -m pytest`) and verify it passes
