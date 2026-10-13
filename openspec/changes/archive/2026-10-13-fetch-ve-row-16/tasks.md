## 1. Fetch the missing row

- [x] 1.1 Change `_fetch_ve_map` in `app/ecu_connection/serial.py` to request rows 1 to 16, and verify by reading the code that the loop bound includes `VE_ROW_16`
- [x] 1.2 Verify against the ECU (or a stub serial answering `#F01` to `#F16`) that the startup log shows `Fuel Map: 15 [...]` with non-zero values and the top table row is populated
- [x] 1.3 Run `openspec validate fetch-ve-row-16 --strict` and verify it passes

## 2. Unit tests

- [x] 2.1 Add `test_all_sixteen_ve_rows_are_requested` and `test_connect_publishes_breakpoints_and_ve_rows_to_the_shared_state` to `tests/test_ecu_connection_serial.py` (stub serial answering `#F01` to `#F16`), and verify the first fails with the old `range(1, 16)` (confirmed by mutation)
- [x] 2.2 Add `test_row_event_refreshes_that_table_row` to `tests/test_ve_calibration_screen.py` covering the highest-MAP table row being populated from the ECU event
- [x] 2.3 Run the full suite (`python -m pytest`) and verify it passes
