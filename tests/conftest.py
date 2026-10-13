import os

# Must be set before any Qt import: run widgets without a display and keep audio noise out.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia*=false")
# Never read the developer's personal config.json while testing: point the loader at a file that does not exist.
os.environ["MI_DASHBOARD_CONFIG_FILE"] = os.path.join(os.path.dirname(__file__), "__no_config__.json")

import pytest
from PyQt6.QtWidgets import QApplication

from app.state.state import vehicle_state


@pytest.fixture(scope="session")
def qapp():
    """One QApplication for the whole run (needed by timers, media objects and widgets)."""
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def clean_vehicle_state():
    """The shared state is a module singleton; give every test a pristine one."""
    vehicle_state.__init__()
    yield
    vehicle_state.__init__()


class RecordingEmitter:
    """Stand-in for the Qt signal the connection thread injects as `emitter`."""

    def __init__(self):
        self.lines = []

    def emit(self, line):
        self.lines.append(line)
