from typing import Callable, Optional

from app.ecu_connection import get_ecu_connection
from app.masterinjection.protocol import EcuCommand
from app.ui.common.row_write_controller import RowWriteController
from app.ui.ignition_tuning.ignition_map_state import IgnitionMapState


class IgnitionWriteController(RowWriteController):
    """
    Debounces ignition offset changes and sends the pending ignition rows (EcuCommand.IGN_ROW_N) after
    1s of inactivity. The write-on-memory command is never sent, so the ECU keeps the change in RAM only.
    `on_finished` runs when the delay elapses, so the analysis knows when the write happened.
    """

    def __init__(self, sound_file: str, state: IgnitionMapState,
                 on_finished: Optional[Callable[[], None]] = None, parent=None):
        super().__init__(
            sound_file,
            pending_rows=state.get_pending_rows,
            row_values=state.get_row_raw_values,
            mark_sent=state.mark_row_sent,
            command_for_row=lambda row: EcuCommand[f"IGN_ROW_{row + 1}"],
            send_command=lambda cmd, values: get_ecu_connection().send_command(cmd, values),
            on_finished=on_finished,
            parent=parent,
        )
