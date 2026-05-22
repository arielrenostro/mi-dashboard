import logging

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from pyqtgraph.Qt.QtCore import Slot

from app.master.ecu import EcuCommand
from app.ve_calibration.ve_map_state import ve_map_state

logger = logging.getLogger(__name__)


class VeWriteController(QObject):
    """
    Debounces VE map edits and sends only the modified rows to the ECU after 1s of inactivity.

    For each pending row, emits command_requested(EcuCommand.VE_ROW_N, [raw_values...]).
    After emitting, marks the row as sent so it is not re-sent unless edited again.
    Plays a single beep when the batch is dispatched.
    """

    # (EcuCommand, list[int]) — connect to EcuConnection.send_command
    command_requested = pyqtSignal(object, object)

    def __init__(self, sound_file: str, parent=None):
        super().__init__(parent)

        self._audio_output = QAudioOutput()
        self._audio_output.setVolume(1.0)
        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio_output)
        self._player.setSource(QUrl.fromLocalFile(sound_file))

        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._send_pending_rows)

    @Slot()
    def on_adjustment_made(self):
        """Restart the 1s debounce timer on every VE edit."""
        self._timer.stop()
        self._timer.start(1000)

    def _send_pending_rows(self):
        pending = ve_map_state.get_pending_rows()

        if not pending:
            logger.debug("Nenhuma linha VE pendente para enviar")
            return

        logger.info("VE write: %d linha(s) a enviar: %s", len(pending), pending)

        for row in pending:
            values = ve_map_state.get_row_raw_values(row)
            cmd = EcuCommand.ve_row(row)
            logger.debug("Enviando %s: %s", cmd.cmd, values)
            ve_map_state.mark_row_sent(row)   # remove da fila ANTES de emitir
            self.command_requested.emit(cmd, values)

        self._player.stop()
        self._player.play()
