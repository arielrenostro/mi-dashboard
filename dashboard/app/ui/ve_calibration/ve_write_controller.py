from app.ecu_connection import get_ecu_connection
from app.masterinjection.protocol import EcuCommand
from app.ui.common.row_write_controller import RowWriteController
from app.ui.ve_calibration.ve_map_state import ve_map_state


class VeWriteController(RowWriteController):
    """
    Debounces VE map edits and sends only the modified rows to the ECU after 1s of inactivity.

    For each pending row, sends EcuCommand.VE_ROW_N with the row's raw values.
    After emitting, marks the row as sent so it is not re-sent unless edited again.
    Plays a single beep when the batch is dispatched.
    """

    def __init__(self, sound_file: str, parent=None):
        super().__init__(
            sound_file,
            pending_rows=lambda: ve_map_state.get_pending_rows(),
            row_values=lambda row: ve_map_state.get_row_raw_values(row),
            mark_sent=lambda row: ve_map_state.mark_row_sent(row),
            command_for_row=lambda row: EcuCommand[f"VE_ROW_{row + 1}"],
            send_command=lambda cmd, values: get_ecu_connection().send_command(cmd, values),
            parent=parent,
        )
