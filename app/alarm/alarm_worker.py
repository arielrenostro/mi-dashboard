import time

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtCore import QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

ALARM_DURATION = 2

class AlarmWorker(QThread):
    emitter = pyqtSignal(bool)

    def __init__(self, sound):
        super().__init__()

        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(1.0)

        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)
        self.player.setSource(QUrl.fromLocalFile(sound))

        self.running = True
        self.alarms = {}

        self.player.mediaStatusChanged.connect(self.handle_status)

    def run(self):
        while self.running:
            try:
                if self.should_play():
                    if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                        self.player.play()
                        self.emitter.emit(True)
                else:
                    if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                        self.player.stop()
                        self.emitter.emit(False)
            except Exception as e:
                print(e)
            self.msleep(100)

    def stop(self):
        self.player.stop()
        self.running = False

    def handle_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.should_play():
                self.player.play()

    def should_play(self):
        if len(self.alarms) == 0:
            return False
        max_ = max(self.alarms.values())
        return time.time() - max_ < ALARM_DURATION

    def set_alarm_state(self, signal, active):
        if active:
            self.alarms[signal] = time.time()

    def is_alarm_firing(self, signal):
        last_triggered = self.alarms.get(signal)
        if last_triggered:
            return time.time() - last_triggered < ALARM_DURATION
        return False
