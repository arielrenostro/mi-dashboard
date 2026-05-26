from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QStackedWidget

from app.config import config
from app.event.app_events import AppEventType
from app.event.bus import event_bus
from app.masterinjection.signal_processor import SignalProcessor
from app.ui.dashboard.screen import DashboardScreen
from app.ui.home.screen import HomeScreen
from app.ui.ve_calibration.screen import VeCalibrationScreen


class AppWindow(QWidget):
    """Main application window that manages multiple screens."""

    key_event    = pyqtSignal(int)
    key_released = pyqtSignal(int)

    def __init__(self, signal_processor: SignalProcessor):
        super().__init__()
        self._signal_processor = signal_processor

        self.stacked_widget = QStackedWidget()
        self.setLayout(self._create_layout())

        self._screens = {}
        self._current_screen_name = None

        self._register_screens()

        event_bus.subscribe(AppEventType.SCREEN_REQUESTED,
                            lambda e: self.show_screen(e.screen_name))

        self.showFullScreen()
        self.show_screen("home")

    def _register_screens(self):
        home_screen = HomeScreen(close_fn=lambda: self.close())

        ve_calibration_screen = VeCalibrationScreen(close_fn=lambda: self.show_screen("home"))

        dashboard_screen = DashboardScreen(
            close_fn=lambda: self.show_screen("home"),
            grid=config.dashboard.grid,
            graphs=config.dashboard.graph,
            graph_x_size=config.dashboard.graph_x_size,
        )

        self._register_screen("home", home_screen)
        self._register_screen("dashboard", dashboard_screen)
        self._register_screen("ve_calibration", ve_calibration_screen)

    def _register_screen(self, name: str, screen):
        self._screens[name] = screen
        self.stacked_widget.addWidget(screen)

    def _create_layout(self):
        from PyQt6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stacked_widget)
        return layout

    def show_screen(self, name: str):
        """Show a screen by name. Calls on_deactivated on old, on_activated on new."""
        if name not in self._screens:
            raise ValueError(f"Screen '{name}' not registered")

        if self._current_screen_name is not None:
            old_screen = self._screens[self._current_screen_name]
            old_screen.on_deactivated()

        new_screen = self._screens[name]
        self.stacked_widget.setCurrentWidget(new_screen)
        self._current_screen_name = name
        new_screen.on_activated()

    def keyPressEvent(self, event):
        """Handle key press events."""
        self._screens[self._current_screen_name].keyPressEvent(event)
        self.key_event.emit(event.key())
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Handle key release events."""
        self._screens[self._current_screen_name].keyReleaseEvent(event)
        self.key_released.emit(event.key())
        super().keyReleaseEvent(event)
