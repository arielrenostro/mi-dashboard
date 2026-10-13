from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class ErrorOverlay(QFrame):
    """Square, dialog-like message shown over its parent for a couple of seconds.

    It never takes focus and ignores the mouse, so keys keep going to the active screen, and a new message
    replaces the current one and restarts the countdown.
    """

    SIZE = 360
    DURATION_MS = 2000
    MAX_MESSAGE_CHARS = 240
    TITLE = "Erro de conexão"

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("errorOverlay")
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet(
            "#errorOverlay { background-color: #2b0d0d; border: 3px solid #e74c3c; border-radius: 12px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title_font = QFont("Arial", 22)
        title_font.setBold(True)
        self._title = self._label(self.TITLE, title_font, "#ff6b5b")
        message_font = QFont("Arial", 16)
        self._message = self._label("", message_font, "#f0f0f0")
        self._message.setWordWrap(True)
        layout.addWidget(self._title)
        layout.addWidget(self._message, stretch=1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self.DURATION_MS)
        self._timer.timeout.connect(self.hide)

        self.hide()

    @staticmethod
    def _label(text: str, font: QFont, color: str) -> QLabel:
        label = QLabel(text)
        label.setFont(font)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"color: {color}; background: transparent;")
        label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        return label

    def show_message(self, message: str):
        if len(message) > self.MAX_MESSAGE_CHARS:
            message = message[: self.MAX_MESSAGE_CHARS - 1] + "…"
        self._message.setText(message)
        self.reposition()
        self.raise_()
        self.show()
        self._timer.start()  # restarts the countdown when it is already running

    def reposition(self):
        parent = self.parentWidget()
        if parent is not None:
            self.move((parent.width() - self.width()) // 2, (parent.height() - self.height()) // 2)
