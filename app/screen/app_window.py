from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QStackedWidget

from app.screen.screen import Screen


class AppWindow(QWidget):
    """Main application window that manages multiple screens."""

    key_event = pyqtSignal(int)
    key_released = pyqtSignal(int)

    def __init__(self):
        super().__init__()

        self.stacked_widget = QStackedWidget()
        self.setLayout(self._create_layout())

        self._screens = {}
        self._current_screen_name = None

        self.showFullScreen()

    def _create_layout(self):
        from PyQt6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stacked_widget)
        return layout

    def register_screen(self, name: str, screen: Screen):
        """Register a Screen with a name."""
        self._screens[name] = screen
        self.stacked_widget.addWidget(screen)

    def show_screen(self, name: str):
        """Show a screen by name. Calls on_deactivated on old, on_activated on new."""
        if name not in self._screens:
            raise ValueError(f"Screen '{name}' not registered")

        # Deactivate current screen
        if self._current_screen_name is not None:
            old_screen = self._screens[self._current_screen_name]
            old_screen.on_deactivated()

        # Activate new screen
        new_screen = self._screens[name]
        self.stacked_widget.setCurrentWidget(new_screen)
        self._current_screen_name = name
        new_screen.on_activated()

    def go_home(self):
        """Navigate to the home screen."""
        self.show_screen("home")

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_Escape:
            self.go_home()
        else:
            self.key_event.emit(event.key())
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Handle key release events."""
        self.key_released.emit(event.key())
        super().keyReleaseEvent(event)
