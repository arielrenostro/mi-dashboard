import logging

from PyQt6.QtCore import QObject, pyqtSignal, QUrl, Qt
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

logger = logging.getLogger(__name__)

_TRIGGER_KEYS = (Qt.Key.Key_Return, Qt.Key.Key_Enter)


class EventMarker(QObject):
    event_triggered = pyqtSignal()

    def __init__(self, sound: str):
        super().__init__()
        self._audio_output = QAudioOutput()
        self._audio_output.setVolume(1.0)
        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio_output)
        self._player.setSource(QUrl.fromLocalFile(sound))

    def handle_key(self, key: int):
        if key in _TRIGGER_KEYS:
            self._mark()

    def _mark(self):
        self._player.stop()
        self._player.play()
        self.event_triggered.emit()
