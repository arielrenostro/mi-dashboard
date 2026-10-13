## 1. Configuration

- [ ] 1.1 Add `mock_skip_lines` (int, default 0) to the connection config in `app/config.py` and verify it loads from JSON and defaults to 0 when absent

## 2. Mock source

- [ ] 2.1 Pass the setting to `EcuConnectionMock` from `main.py` and replace the literal 12250 in `app/ecu_connection/mock_log.py`, then verify with a small CSV that a skip of 0 emits from the first data line and a skip of N starts at line N+1
- [ ] 2.2 Verify the replay restarts from the first data line after the end of the file

## 3. Documentation and verification

- [ ] 3.1 Add `connection.mock_skip_lines` to the README configuration table
- [ ] 3.2 Run `openspec validate mock-skip-lines-config --strict` and verify it passes

## 4. Unit tests

- [ ] 4.1 Add tests to `tests/test_app_configuration.py`: `connection.mock_skip_lines` defaults to 0 and loads from JSON
- [ ] 4.2 Create `tests/test_ecu_connection_mock.py` (temp CSV, patched `time.sleep`): skip 0 emits from the first data line; skip N starts at line N+1; the replay restarts from the first data line without skipping again; lines are emitted trimmed at one per 0.1 s; fixed breakpoints and VE map are published at start
- [ ] 4.3 Run the full suite (`python -m pytest`) and verify it passes
