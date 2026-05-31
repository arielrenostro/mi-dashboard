from typing import Callable

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget

from app.event.app_events import AppEventType
from app.event.bus import event_bus


class Screen(QWidget):
    """Base class for all screens in the multi-screen architecture."""

    screen_requested = pyqtSignal(str)

    def __init__(self, close_fn: Callable):
        super().__init__()
        self.close_fn = close_fn
        self._bus_tokens: list = []

    def _subscribe(self, event_type: AppEventType, callback) -> None:
        token = event_bus.subscribe(event_type, callback)
        self._bus_tokens.append(token)

    def on_activated(self):
        """Called when this screen becomes active."""

    def on_deactivated(self):
        """Called when this screen is hidden."""
        for token in self._bus_tokens:
            event_bus.unsubscribe(token)
        self._bus_tokens.clear()
