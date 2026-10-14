import logging
from typing import Callable, List, Optional

from PyQt6.QtCore import QObject, QTimer, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from pyqtgraph.Qt.QtCore import Slot

from app.masterinjection.protocol import EcuCommand

logger = logging.getLogger(__name__)

WRITE_DELAY_MS = 1000


class RowWriteController(QObject):
    """
    Debounces map edits and sends only the pending rows to the ECU after 1 s of inactivity.

    The map it writes is described by callables, so one controller serves the VE map and the ignition map:
    which rows are pending, the 16 raw values of a row, how to mark a row as sent, which command writes
    a row and how to send a command. Each row is marked as sent before its command is queued, so it is
    not written again unless edited again. A single beep plays when at least one row was dispatched.
    `on_finished` is called every time the delay elapses, whether or not anything was sent.
    """

    def __init__(self, sound_file: str,
                 pending_rows: Callable[[], List[int]],
                 row_values: Callable[[int], List[int]],
                 mark_sent: Callable[[int], None],
                 command_for_row: Callable[[int], EcuCommand],
                 send_command: Callable[[EcuCommand, List[int]], None],
                 on_finished: Optional[Callable[[], None]] = None,
                 parent=None):
        super().__init__(parent)
        self._pending_rows = pending_rows
        self._row_values = row_values
        self._mark_sent = mark_sent
        self._command_for_row = command_for_row
        self._send_command = send_command
        self._on_finished = on_finished

        self._audio_output = QAudioOutput()
        self._audio_output.setVolume(1.0)
        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio_output)
        self._player.setSource(QUrl.fromLocalFile(sound_file))

        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._send_pending_rows)

    def set_muted(self, muted: bool):
        """Silence the confirmation beep (used while the owning screen is hidden)."""
        self._audio_output.setMuted(muted)

    @Slot()
    def on_adjustment_made(self):
        """Restart the 1s debounce timer on every edit."""
        self._timer.stop()
        self._timer.start(WRITE_DELAY_MS)

    def _send_pending_rows(self):
        try:
            self._dispatch()
        finally:
            if self._on_finished is not None:
                self._on_finished()

    def _dispatch(self):
        pending = self._pending_rows()

        if not pending:
            logger.debug("Nenhuma linha pendente para enviar")
            return

        logger.info("Write: %d linha(s) a enviar: %s", len(pending), pending)

        for row in pending:
            values = self._row_values(row)
            cmd = self._command_for_row(row)
            logger.debug("Enviando %s: %s", cmd.cmd, values)
            self._mark_sent(row)   # remove da fila ANTES de emitir
            self._send_command(cmd, values)

        self._player.stop()
        self._player.play()
