from typing import Callable

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QWidget, QHBoxLayout

from app.config import config
from app.ecu_connection import get_ecu_connection
from app.ecu_connection.ecu_connection import EcuConnectionStatus
from app.ui.base.screen import Screen


class HomeScreen(Screen):
    """Home screen with a keyboard-navigable menu."""

    screen_requested = pyqtSignal(str)

    def __init__(self, close_fn: Callable):
        super().__init__(close_fn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(40)
        layout.addStretch()

        self.setStyleSheet("background-color:black;")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Title
        title = QLabel("Master Injection")
        title_font = QFont("Arial", 48)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Status
        status_font = QFont("Arial", 14)
        status_connection = QLabel()
        status_connection.setFont(status_font)
        status_connection.setStyleSheet("color: white;")
        if config.connection.mock != '':
            if len(config.connection.mock) > 40:
                status_connection.setText(f"Mock: ...{config.connection.mock[-40:]} | ")
            else:
                status_connection.setText(f"Mock: {config.connection.mock} | ")
        else:
            status_connection.setText(f"Port: {config.connection.port} | Baudrate: {config.connection.baudrate} | ")

        status_dot = QLabel()
        status_dot.setFixedSize(12, 12)

        status_label = QLabel()
        status_label.setFont(status_font)
        status_label.setStyleSheet("color: white;")

        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(8)
        status_layout.addWidget(status_connection)
        status_layout.addWidget(status_dot)
        status_layout.addWidget(status_label)
        status_layout.addStretch()

        status_container = QWidget()
        status_container.setLayout(status_layout)
        layout.addWidget(status_container, alignment=Qt.AlignmentFlag.AlignCenter)

        def _update_status():
            status = get_ecu_connection().get_connection_status()
            if status == EcuConnectionStatus.CONNECTED:
                status_label.setText("Connected")
                status_dot.setStyleSheet("background-color: #2ecc71; border-radius: 6px;")
            elif status == EcuConnectionStatus.CONNECTING:
                status_label.setText("Connecting")
                status_dot.setStyleSheet("background-color: #e7c53c; border-radius: 6px;")
            elif status == EcuConnectionStatus.HANDSHAKE:
                status_label.setText("Handshake")
                status_dot.setStyleSheet("background-color: #e7c53c; border-radius: 6px;")
            elif status == EcuConnectionStatus.ERROR:
                status_label.setText("Error")
                status_dot.setStyleSheet("background-color: #e74c3c; border-radius: 6px;")
            elif status == EcuConnectionStatus.DISCONNECTED:
                status_label.setText("Disconnected")
                status_dot.setStyleSheet("background-color: #e74c3c; border-radius: 6px;")
            else:
                status_label.setText("Unknow")
                status_dot.setStyleSheet("background-color: gray; border-radius: 6px;")

        self._status_timer = QTimer()
        self._status_timer.timeout.connect(_update_status)

        # Menu items container
        menu_container = QWidget()
        menu_layout = QVBoxLayout(menu_container)
        menu_layout.setContentsMargins(0, 0, 0, 0)
        menu_layout.setSpacing(10)

        self._menu_items = [
            ("Dashboard", "dashboard"),
            ("Calibração de VE", "ve_calibration"),
        ]

        self._menu_labels = []
        for display_name, screen_name in self._menu_items:
            label = QLabel(display_name)
            label_font = QFont("Arial", 24)
            label.setFont(label_font)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._menu_labels.append(label)
            menu_layout.addWidget(label)

        layout.addWidget(menu_container, alignment=Qt.AlignmentFlag.AlignCenter)

        # Keyboard hint at bottom
        hint = QLabel("↑↓ Navegar | Enter Selecionar")
        hint_font = QFont("Arial", 14)
        hint.setFont(hint_font)
        hint.setStyleSheet("color: gray;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        layout.addStretch()

        self._selected = 0
        self._update_selection_ui()

    def on_activated(self):
        self._status_timer.start(500)

    def on_deactivated(self):
        self._status_timer.stop()

    def _update_selection_ui(self):
        """Update the visual state of menu items based on selection."""
        for i, label in enumerate(self._menu_labels):
            if i == self._selected:
                label.setStyleSheet(
                    "color: white; "
                    "border: 2px solid #1E90FF; "
                    "background-color: rgba(30, 144, 255, 0.2); "
                    "padding: 10px;"
                )
            else:
                label.setStyleSheet(
                    "color: gray; "
                    "border: 2px solid transparent; "
                    "background-color: transparent; "
                    "padding: 10px;"
                )

    def keyPressEvent(self, event):
        """Handle keyboard navigation."""
        if event.isAutoRepeat():
            return

        if event.key() == Qt.Key.Key_Up:
            self._selected = (self._selected - 1) % len(self._menu_items)
            self._update_selection_ui()
        elif event.key() == Qt.Key.Key_Down:
            self._selected = (self._selected + 1) % len(self._menu_items)
            self._update_selection_ui()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            _, screen_name = self._menu_items[self._selected]
            self.screen_requested.emit(screen_name)
        else:
            super().keyPressEvent(event)
