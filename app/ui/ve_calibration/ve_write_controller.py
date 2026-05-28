import logging

from PyQt6.QtCore import QObject, QTimer, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from pyqtgraph.Qt.QtCore import Slot

from app.ecu import get_ecu_session
from app.ui.ve_calibration.ve_map_state import ve_map_state

logger = logging.getLogger(__name__)


class VeWriteController(QObject):
    """
    Debounces VE map edits and sends only the modified rows to the ECU after 1s of inactivity.
    Plays a single beep when the batch is dispatched.
    """

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

        session = get_ecu_session()
        for row in pending:
            values = ve_map_state.get_row_raw_values(row)
            logger.debug("Enviando VE row %d: %s", row + 1, values)
            ve_map_state.mark_row_sent(row)   # remove da fila ANTES de emitir
            session.set_ve_row(row, values)

        self._player.stop()
        self._player.play()
