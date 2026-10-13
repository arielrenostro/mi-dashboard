"""Spec: openspec/specs/screen-navigation (full-screen window, lifecycle, key routing)."""
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import Qt

from app.masterinjection.signal_processor import SignalProcessor
from app.ui.window import AppWindow
from tests.helpers import SAMPLE_FRAME, key_press


@pytest.fixture
def processor():
    return SignalProcessor()


@pytest.fixture
def window(qapp, processor):
    w = AppWindow(processor)
    yield w
    w.close()


def test_window_registers_the_three_screens_and_starts_on_home(window):
    """Requirement: Full-screen multi-screen window."""
    assert set(window._screens) == {"home", "dashboard", "ve_calibration"}
    assert window._current_screen_name == "home"
    assert window.stacked_widget.currentWidget() is window._screens["home"]


def test_window_is_full_screen(window):
    assert window.isFullScreen()


def test_show_screen_switches_the_visible_screen(window):
    window.show_screen("dashboard")

    assert window.stacked_widget.currentWidget() is window._screens["dashboard"]
    assert window._current_screen_name == "dashboard"


def test_lifecycle_hooks_run_in_order_on_switch(window):
    """Scenario: Switch."""
    calls = []
    home, dashboard = window._screens["home"], window._screens["dashboard"]
    home.on_deactivated = lambda: calls.append("home hidden")
    dashboard.on_activated = lambda: calls.append(
        f"dashboard active (visible={window.stacked_widget.currentWidget() is dashboard})"
    )

    window.show_screen("dashboard")

    assert calls == ["home hidden", "dashboard active (visible=True)"]


def test_unknown_screen_is_an_error_and_keeps_the_current_screen(window):
    """Scenario: Unknown screen."""
    with pytest.raises(ValueError):
        window.show_screen("does_not_exist")

    assert window._current_screen_name == "home"


def test_home_menu_selection_opens_the_screen(window):
    """Scenario: Open (through the real signal wiring)."""
    window._screens["home"].keyPressEvent(key_press(Qt.Key.Key_Down))
    window._screens["home"].keyPressEvent(key_press(Qt.Key.Key_Return))

    assert window._current_screen_name == "ve_calibration"


def test_key_events_go_only_to_the_visible_screen(window):
    """Requirement: Keyboard routing."""
    for name, screen in window._screens.items():
        screen.keyPressEvent = Mock(name=name)
        screen.keyReleaseEvent = Mock(name=name)
    window.show_screen("ve_calibration")
    event = key_press(Qt.Key.Key_R)

    window.keyPressEvent(event)
    window.keyReleaseEvent(event)

    visible = window._screens["ve_calibration"]
    visible.keyPressEvent.assert_called_once_with(event)
    visible.keyReleaseEvent.assert_called_once_with(event)
    for name in ("home", "dashboard"):
        window._screens[name].keyPressEvent.assert_not_called()
        window._screens[name].keyReleaseEvent.assert_not_called()


@pytest.mark.parametrize("screen", ["dashboard", "ve_calibration"])
def test_escape_returns_to_home_from_data_screens(window, screen):
    """Requirement: Return to Home with ESC (Scenario: Back from calibration)."""
    window.show_screen(screen)

    window.keyPressEvent(key_press(Qt.Key.Key_Escape))

    assert window._current_screen_name == "home"


def test_dashboard_receives_frames_from_the_signal_processor(window, processor):
    """Requirement: Live update (wiring between the processor and the Dashboard)."""
    processor.process_line(SAMPLE_FRAME)

    from app.masterinjection.signal import Signal

    assert window._screens["dashboard"].labels[Signal.RPM].big_label.text() == "3415"
