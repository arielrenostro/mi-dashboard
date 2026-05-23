import logging
from typing import Dict

from PyQt6.QtCore import QThread, pyqtSignal, QUrl, Qt
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from app.masterinjection.signal import Signal, ParsedSignal
from app.state.state import vehicle_state

logger = logging.getLogger(__name__)


class AlarmProcessor(QThread):
    emitter = pyqtSignal(Signal)
    _play_requested = pyqtSignal()
    _stop_requested = pyqtSignal()

    def __init__(self, sound):
        super().__init__()

        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(1.0)

        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)
        self.player.setSource(QUrl.fromLocalFile(sound))
        self.player.mediaStatusChanged.connect(self._handle_status)

        # QueuedConnection: garante execução na main thread independente de qual
        # thread emite o sinal. AlarmProcessor e player têm o mesmo thread owner
        # (main thread), então o Qt usaria DirectConnection por padrão — o que
        # chamaria play/stop na worker thread, violando o thread affinity do player.
        self._play_requested.connect(self.player.play, Qt.ConnectionType.QueuedConnection)
        self._stop_requested.connect(self.player.stop, Qt.ConnectionType.QueuedConnection)

        self.running = True

    def run(self):
        is_playing = False
        while self.running:
            try:
                should_play = vehicle_state.is_any_alarm_firing()
                if should_play and not is_playing:
                    self._play_requested.emit()
                    is_playing = True
                elif not should_play and is_playing:
                    self._stop_requested.emit()
                    is_playing = False
            except Exception:
                logger.exception("Erro no loop do AlarmProcessor")
            self.msleep(100)

    def stop(self):
        self._stop_requested.emit()
        self.running = False

    def process_signals(self, signals: Dict[Signal, ParsedSignal]):
        for signal, data in signals.items():
            alarm = signal.value["alarm"]

            in_alarm = False
            min_ = alarm["min"] if alarm["min"] is None or isinstance(alarm["min"], (int, float)) else alarm["min"](data.value)
            max_ = alarm["max"] if alarm["max"] is None or isinstance(alarm["max"], (int, float)) else alarm["max"](data.value)

            if min_ is not None and data.value < min_:
                in_alarm = alarm["enabled"]
            elif max_ is not None and data.value > max_:
                in_alarm = alarm["enabled"]

            if in_alarm and not vehicle_state.is_alarm_firing(signal):
                self.emitter.emit(signal)
            vehicle_state.set_alarm(signal, in_alarm)

    def _handle_status(self, status):
        # chamado na main thread (affinity do player) — player.play() é seguro aqui
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if vehicle_state.is_any_alarm_firing():
                self.player.play()
