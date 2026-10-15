import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QStackedWidget

from app.config import config
from app.masterinjection.signal_processor import SignalProcessor
from app.ui.components.error_overlay import ErrorOverlay
from app.ui.dashboard.screen import DashboardScreen
from app.ui.home.screen import HomeScreen
from app.ui.ignition_tuning.screen import IgnitionTuningScreen
from app.ui.options.screen import OptionsScreen
from app.ui.ve_calibration.screen import VeCalibrationScreen

logger = logging.getLogger(__name__)


class AppWindow(QWidget):
    """Main application window that manages multiple screens."""

    # Announces every non-repeating key press made on a data screen (Dashboard, VE calibration or ignition tuning).
    key_event = pyqtSignal(int)

    _DATA_SCREENS = ("dashboard", "ve_calibration", "ignition_tuning")

    # Global shortcuts: handled here, on every screen, and never delivered to the screens.
    _SHORTCUTS = {
        Qt.Key.Key_F1: "dashboard",
        Qt.Key.Key_F2: "ve_calibration",
        Qt.Key.Key_F3: "ignition_tuning",
        Qt.Key.Key_F4: "options",
    }

    def __init__(self, signal_processor: SignalProcessor):
        super().__init__()
        self.setWindowTitle("Master Injection Dashboard")
        self._signal_processor = signal_processor

        self.stacked_widget = QStackedWidget()
        self.setLayout(self._create_layout())
        self._error_overlay = ErrorOverlay(self)

        self._screens = {}
        self._current_screen_name = None

        self._register_screens()

        self.showFullScreen()
        self.show_screen("home")

    def _register_screens(self):
        home_screen = HomeScreen(close_fn=lambda: self.close() )
        home_screen.screen_requested.connect(lambda x: self.show_screen(x))

        ve_calibration_screen = VeCalibrationScreen(close_fn=lambda: self.show_screen("home"))

        ignition_tuning_screen = IgnitionTuningScreen(close_fn=lambda: self.show_screen("home"))
        self._signal_processor.emitter.connect(ignition_tuning_screen.on_signal_received)

        options_screen = OptionsScreen(close_fn=lambda: self.show_screen("home"))

        dashboard_screen = DashboardScreen(
            close_fn=lambda: self.show_screen("home"),
            grid=config.dashboard.grid,
            graphs=config.dashboard.graph,
            graph_x_size=config.dashboard.graph_x_size,
        )
        self._signal_processor.emitter.connect(dashboard_screen.on_signal_received)

        self._register_screen(
            "home",
            home_screen,
        )
        self._register_screen(
            "dashboard",
            dashboard_screen,
        )
        self._register_screen(
            "ve_calibration",
            ve_calibration_screen,
        )
        self._register_screen(
            "ignition_tuning",
            ignition_tuning_screen,
        )
        self._register_screen(
            "options",
            options_screen,
        )

    def on_connection_error(self, message: str):
        """Show a connection error over the current screen for a couple of seconds."""
        self._error_overlay.show_message(message)

    def closeEvent(self, event):
        """Write the pending ignition results before the window goes away (closing twice is harmless)."""
        try:
            self._screens["ignition_tuning"].flush_results()
        except Exception:
            logger.exception("Could not write the ignition results")
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._error_overlay.isVisible():
            self._error_overlay.reposition()

    def on_ecu_line(self, line: str):
        """Forward a raw line from the ECU to the Options screen (it handles the #X02 answers)."""
        self._screens["options"].on_ecu_line(line)

    def on_alarm_onset(self, signal):
        """Forward the alarm onset notification to the Dashboard so the signal's card flashes."""
        self._screens["dashboard"].fire_field_alarm(signal)

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

        # Deactivate current screen
        if self._current_screen_name is not None:
            old_screen = self._screens[self._current_screen_name]
            old_screen.on_deactivated()

        # Activate new screen
        new_screen = self._screens[name]
        self.stacked_widget.setCurrentWidget(new_screen)
        self._current_screen_name = name
        new_screen.on_activated()

    def keyPressEvent(self, event):
        """Handle key press events."""
        shortcut_screen = self._SHORTCUTS.get(event.key())
        if shortcut_screen is not None:
            if not event.isAutoRepeat() and shortcut_screen != self._current_screen_name:
                self.show_screen(shortcut_screen)
            return

        # Judge the screen before the key is handled: Enter on Home opens a screen and must not be announced.
        announce = self._current_screen_name in self._DATA_SCREENS and not event.isAutoRepeat()
        self._screens[self._current_screen_name].keyPressEvent(event)
        super().keyPressEvent(event)
        if announce:
            self.key_event.emit(int(event.key()))

    def keyReleaseEvent(self, event):
        """Handle key release events."""
        if event.key() in self._SHORTCUTS:
            return
        self._screens[self._current_screen_name].keyReleaseEvent(event)
        super().keyReleaseEvent(event)
