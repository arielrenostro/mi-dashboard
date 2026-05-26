import logging

from PyQt6.QtCore import QObject, QUrl, Qt
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from app.event.app_events import EventMarkRequestedEvent
from app.event.bus import event_bus

logger = logging.getLogger(__name__)

_TRIGGER_KEYS = (Qt.Key.Key_Return, Qt.Key.Key_Enter)


class EventMarker(QObject):

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
        event_bus.publish(EventMarkRequestedEvent())
