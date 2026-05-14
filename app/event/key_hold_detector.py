from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt


class KeyHoldDetector(QObject):
    triggered = pyqtSignal()

    def __init__(self, key: Qt.Key, hold_ms: int = 2000):
        super().__init__()
        self._key = key
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(hold_ms)
        self._timer.timeout.connect(self.triggered)

    def on_key_pressed(self, key: int):
        if key == self._key and not self._timer.isActive():
            self._timer.start()

    def on_key_released(self, key: int):
        if key == self._key:
            self._timer.stop()
