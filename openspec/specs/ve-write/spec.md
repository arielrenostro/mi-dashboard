## ADDED Requirements

### Requirement: VE edits are debounced 1 second before sending to ECU
`VeWriteController` MUST use a single-shot `QTimer` (1000 ms). Every time the VE map is adjusted or reset, `VeCalibrationScreen` MUST call `self._writer.on_adjustment_made()` directly. `on_adjustment_made()` MUST cancel any pending timer and restart it at 1000 ms. The ECU write MUST be dispatched only after 1 second of inactivity.

#### Scenario: Rapid edits produce a single write
- **WHEN** the operator presses ↑ five times in 800 ms
- **THEN** only one batch of ECU commands SHALL be sent (after the final keypress + 1 s)

#### Scenario: Single edit is sent after 1 second
- **WHEN** one VE adjustment is made and no further edits occur
- **THEN** the ECU write SHALL be dispatched 1 second later

### Requirement: Only modified rows are sent to the ECU
`_send_pending_rows()` MUST call `ve_map_state.get_pending_rows()`. If the list is empty, it MUST return without sending any commands. For each pending row, it MUST:
1. Retrieve full 16-cell row values via `ve_map_state.get_row_raw_values(row)`
2. Resolve command `EcuCommand[f"VE_ROW_{row + 1}"]`
3. Call `ve_map_state.mark_row_sent(row)` before dispatching
4. Call `get_ecu_connection().send_command(cmd, values)`

#### Scenario: Only changed rows are sent
- **WHEN** only rows 3 and 7 have been modified
- **THEN** only `VE_ROW_4` and `VE_ROW_8` commands SHALL be sent

#### Scenario: No commands sent when map has no pending changes
- **WHEN** the debounce timer fires and no cells have been modified
- **THEN** no ECU commands SHALL be sent

### Requirement: Audio feedback confirms the write dispatch
After dispatching all pending rows, `VeWriteController` MUST play `ve_sound` (stop any current playback first, then play from start). All `QMediaPlayer` calls MUST happen on the main Qt thread.

#### Scenario: Beep plays after write
- **WHEN** one or more modified rows are sent to the ECU
- **THEN** `ve_sound` SHALL play once

### Requirement: VeWriteController is owned by VeCalibrationScreen with no external wiring
`VeWriteController` MUST be instantiated inside `VeCalibrationScreen`. No external signals or bus subscriptions are required. `VeCalibrationScreen` calls `on_adjustment_made()` directly.

#### Scenario: Write controller requires no external wiring
- **WHEN** `VeCalibrationScreen` is instantiated
- **THEN** `VeWriteController` SHALL be created and fully functional without any wiring in `main.py`
