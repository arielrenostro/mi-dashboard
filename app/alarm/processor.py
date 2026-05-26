import logging
import time
from typing import Dict

from PyQt6.QtCore import QThread, pyqtSignal, QUrl, Qt
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from app.event.app_events import AppEventType, AlarmFiredEvent, SignalsReceivedEvent
from app.event.bus import event_bus
from app.masterinjection.signal import Signal, ParsedSignal
from app.state.state import vehicle_state

logger = logging.getLogger(__name__)


class AlarmProcessor(QThread):
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

        self._alarm_until: Dict[Signal, float] = {}

        event_bus.subscribe(AppEventType.SIGNALS_RECEIVED, self._on_signals_received)

        self.running = True

    def _on_signals_received(self, event: SignalsReceivedEvent):
        self.process_signals(event.data)

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
        now = time.time()
        for signal, data in signals.items():
            alarm = signal.value["alarm"]
            duration = alarm.get("duration_s", 2.0)

            in_alarm = self._check_in_alarm(alarm, data)
            vehicle_state.set_alarm(signal, in_alarm)

            if in_alarm:
                until = self._alarm_until.get(signal, 0.0)
                if now >= until:
                    new_until = now + duration
                    self._alarm_until[signal] = new_until
                    event_bus.publish(AlarmFiredEvent(signal=signal, until=new_until))
            else:
                self._alarm_until.pop(signal, None)

    @staticmethod
    def _check_in_alarm(alarm: dict, data: ParsedSignal) -> bool:
        min_ = alarm["min"] if alarm["min"] is None or isinstance(alarm["min"], (int, float)) else alarm["min"](data.value)
        max_ = alarm["max"] if alarm["max"] is None or isinstance(alarm["max"], (int, float)) else alarm["max"](data.value)

        if min_ is not None and data.value < min_:
            return alarm["enabled"]
        if max_ is not None and data.value > max_:
            return alarm["enabled"]
        return False

    def _handle_status(self, status):
        # chamado na main thread (affinity do player) — player.play() é seguro aqui
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if vehicle_state.is_any_alarm_firing():
                self.player.play()
