import logging

from PyQt6.QtCore import QObject, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from app.state.state import vehicle_state

logger = logging.getLogger(__name__)


class LambdaToggle(QObject):

    def __init__(self, sound: str):
        super().__init__()
        self._audio_output = QAudioOutput()
        self._audio_output.setVolume(1.0)
        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio_output)
        self._player.setSource(QUrl.fromLocalFile(sound))

    def handle_trigger(self):
        self._player.stop()
        self._player.play()
        if vehicle_state.is_lambda_loop_closed():
            logger.info("Alternando lambda loop: OPEN")
            vehicle_state.open_lambda_loop()
        else:
            logger.info("Alternando lambda loop: CLOSE")
            vehicle_state.close_lambda_loop()
