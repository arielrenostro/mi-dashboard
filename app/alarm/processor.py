from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtCore import QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from app.alarm.state import is_any_alarm_firing, set_alarm_state, is_alarm_firing
from app.master.signal import Signal

ALARM_DURATION = 2


class AlarmProcessor(QThread):
    emitter = pyqtSignal(Signal)

    def __init__(self, sound):
        super().__init__()

        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(1.0)

        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)
        self.player.setSource(QUrl.fromLocalFile(sound))
        self.player.mediaStatusChanged.connect(self._handle_status)

        self.running = True

    def run(self):
        while self.running:
            try:
                if self._should_play():
                    if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                        self.player.play()
                else:
                    if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                        self.player.stop()
            except Exception as e:
                print(e)
            self.msleep(100)

    def stop(self):
        self.player.stop()
        self.running = False

    def process_signals(self, signals):
        for signal, data in signals.items():
            value = data["value"]
            alarm = signal.value["alarm"]

            in_alarm = False
            min_ = alarm["min"] if alarm["min"] is None or isinstance(alarm["min"], (int, float)) else alarm["min"](
                value)
            max_ = alarm["max"] if alarm["max"] is None or isinstance(alarm["max"], (int, float)) else alarm["max"](
                value)

            if min_ is not None and value < min_:
                in_alarm = alarm["enabled"]
            elif max_ is not None and value > max_:
                in_alarm = alarm["enabled"]

            if in_alarm and not is_alarm_firing(signal):
                self.emitter.emit(signal)
            set_alarm_state(signal, in_alarm)

    def _handle_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._should_play():
                self.player.play()

    def _should_play(self):
        return is_any_alarm_firing()
