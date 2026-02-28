import time

import winsound
from PyQt6.QtCore import QThread, pyqtSignal



from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtMultimedia import QSoundEffect, QMediaPlayer, QAudioOutput
from PyQt6.QtCore import QUrl
import time


class AlarmWorker(QObject):

    def __init__(self):
        super().__init__()

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()

        self.player.setAudioOutput(self.audio_output)
        self.player.setSource(QUrl.fromLocalFile("tira-tira-chaves.mp3"))
        # self.player.setSource(QUrl.fromLocalFile("alarm.wav"))
        self.audio_output.setVolume(1.0)

        self.alarm_active = False
        self.last_data_time = time.time()

        self.player.mediaStatusChanged.connect(self.handle_status)

    def handle_status(self, status):
        # Quando terminar, reinicia (loop)
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.should_play():
                self.player.play()

    def should_play(self):
        stream_alive = (time.time() - self.last_data_time) < 1.0
        return self.alarm_active and stream_alive

    def set_alarm_state(self, active: bool):
        self.alarm_active = active
        self.update_state()

    def notify_data_received(self):
        self.last_data_time = time.time()
        self.update_state()

    def update_state(self):
        if self.should_play():
            if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                self.player.play()
        else:
            if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.player.stop()