import logging

from PyQt6.QtCore import QObject, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from app.event.app_events import EcuCommandRequestedEvent
from app.event.bus import event_bus
from app.masterinjection.protocol import EcuCommand
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
            cmd = EcuCommand.LAMBDA_LOOP_OPEN
        else:
            cmd = EcuCommand.LAMBDA_LOOP_CLOSE
        logger.info("Alternando lambda loop: %s", cmd.description)
        event_bus.publish(EcuCommandRequestedEvent(command=cmd))
