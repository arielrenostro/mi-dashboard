import time

from PyQt6.QtCore import QThread
from PyQt6.QtCore import QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput


class AlarmWorker(QThread):

    def __init__(self, sound):
        super().__init__()

        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(1.0)

        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)
        self.player.setSource(QUrl.fromLocalFile(sound))

        self.running = True
        self.alarm_play_until = time.time()
        self.last_data_time = time.time()

        self.player.mediaStatusChanged.connect(self.handle_status)

    def run(self):
        while self.running:
            try:
                if self.should_play():
                    if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                        self.player.play()
                else:
                    if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                        self.player.stop()
            except:
                pass
            time.sleep(0.01)

    def stop(self):
        self.player.stop()
        self.running = False

    def handle_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.should_play():
                self.player.play()

    def should_play(self):
        play_until_active = time.time() < self.alarm_play_until
        return play_until_active

    def set_alarm_state(self, active: bool):
        if not self.should_play() and active:
            self.alarm_play_until = time.time() + 1.0

    def notify_data_received(self):
        self.last_data_time = time.time()
