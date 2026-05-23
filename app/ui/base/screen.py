from typing import Callable

from PyQt6.QtWidgets import QWidget


class Screen(QWidget):
    """Base class for all screens in the multi-screen architecture."""

    def __init__(self, close_fn: Callable):
        super().__init__()
        self.close_fn = close_fn

    def on_activated(self):
        """Called when this screen becomes active."""
        pass

    def on_deactivated(self):
        """Called when this screen is hidden."""
        pass
