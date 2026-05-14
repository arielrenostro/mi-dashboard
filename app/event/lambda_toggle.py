import logging

from PyQt6.QtCore import QObject, pyqtSignal, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from app.master.ecu import EcuCommand
from app.vehicle.state import vehicle_state

logger = logging.getLogger(__name__)


class LambdaToggle(QObject):
    command_requested = pyqtSignal(object)

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
            cmd = EcuCommand.LAMBDA_LOOP_OPEN
        else:
            cmd = EcuCommand.LAMBDA_LOOP_CLOSE
        logger.info("Alternando lambda loop: %s", cmd.description)
        self.command_requested.emit(cmd)
