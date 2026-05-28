from __future__ import annotations

import logging
import time
from typing import Dict

from PyQt6.QtCore import QObject, pyqtSignal, QUrl, Qt, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from app.event.app_events import AppEventType, AlarmFiredEvent, SignalsReceivedEvent
from app.event.bus import event_bus
from app.masterinjection.signal import Signal, ParsedSignal
from app.state.state import vehicle_state

logger = logging.getLogger(__name__)


class AlarmProcessor(QObject):
    _play_requested = pyqtSignal()
    _stop_requested = pyqtSignal()

    def __init__(self, sound: str):
        super().__init__()

        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(1.0)

        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)
        self.player.setSource(QUrl.fromLocalFile(sound))
        self.player.mediaStatusChanged.connect(self._handle_status)

        self._play_requested.connect(self.player.play, Qt.ConnectionType.QueuedConnection)
        self._stop_requested.connect(self.player.stop, Qt.ConnectionType.QueuedConnection)

        self._alarm_until: Dict[Signal, float] = {}
        self._is_playing = False

        event_bus.subscribe(AppEventType.SIGNALS_RECEIVED, self._on_signals_received)

    def start(self) -> None:
        pass  # no thread to start

    def stop(self) -> None:
        self._stop_requested.emit()

    def _on_signals_received(self, event: SignalsReceivedEvent) -> None:
        self.process_signals(event.data)

    def process_signals(self, signals: Dict[Signal, ParsedSignal]) -> None:
        now = time.time()
        for signal, data in signals.items():
            alarm = signal.value.get("alarm")
            if not alarm:
                continue
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

        self._update_audio()

    def _update_audio(self) -> None:
        should_play = vehicle_state.is_any_alarm_firing()
        if should_play and not self._is_playing:
            self._play_requested.emit()
            self._is_playing = True
        elif not should_play and self._is_playing:
            self._stop_requested.emit()
            self._is_playing = False

    @staticmethod
    def _check_in_alarm(alarm: dict, data: ParsedSignal) -> bool:
        if not alarm.get("enabled", False):
            return False
        min_ = alarm["min"] if alarm["min"] is None or isinstance(alarm["min"], (int, float)) else alarm["min"](data.value)
        max_ = alarm["max"] if alarm["max"] is None or isinstance(alarm["max"], (int, float)) else alarm["max"](data.value)
        if min_ is not None and data.value < min_:
            return True
        if max_ is not None and data.value > max_:
            return True
        return False

    def _handle_status(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if vehicle_state.is_any_alarm_firing():
                self.player.play()
            else:
                self._is_playing = False
