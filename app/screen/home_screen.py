from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QWidget

from app.screen.screen import Screen


class HomeScreen(Screen):
    """Home screen with a keyboard-navigable menu."""

    screen_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self.setStyleSheet("background-color: black;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(40)
        layout.addStretch()

        # Title
        title = QLabel("Master Injection")
        title_font = QFont("Arial", 48)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Menu items container
        menu_container = QWidget()
        menu_layout = QVBoxLayout(menu_container)
        menu_layout.setContentsMargins(0, 0, 0, 0)
        menu_layout.setSpacing(20)

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
        hint = QLabel("↑↓ Navegar  Enter Selecionar")
        hint_font = QFont("Arial", 14)
        hint.setFont(hint_font)
        hint.setStyleSheet("color: gray;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        layout.addStretch()

        self._selected = 0
        self._update_selection_ui()

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
