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


def test_escape_on_home_closes_the_window(window):
    """Scenario: Exit from Home (through the real close callback)."""
    window.close = Mock()

    window.keyPressEvent(key_press(Qt.Key.Key_Escape))

    window.close.assert_called_once()


def test_held_escape_does_not_exit_after_returning_to_home(window):
    """Scenario: Held ESC after returning to Home."""
    window.close = Mock()
    window.show_screen("dashboard")

    window.keyPressEvent(key_press(Qt.Key.Key_Escape))  # leaves the Dashboard
    assert window._current_screen_name == "home"
    for _ in range(5):
        window.keyPressEvent(key_press(Qt.Key.Key_Escape, auto_repeat=True))  # the user is still holding it

    window.close.assert_not_called()

    window.keyPressEvent(key_press(Qt.Key.Key_Escape))  # a fresh press

    window.close.assert_called_once()


def test_window_title_is_master_injection_dashboard(window):
    """Requirement: Window title / Scenario: Title shown."""
    assert window.windowTitle() == "Master Injection Dashboard"


# ------------------------------------------------------------------ key signal

@pytest.fixture
def pressed(window):
    """Keys announced by the window's key signal."""
    keys = []
    window.key_event.connect(keys.append)
    return keys


@pytest.mark.parametrize("screen", ["dashboard", "ve_calibration"])
def test_key_signal_is_emitted_on_the_data_screens(window, pressed, screen):
    """Requirement: Manual event mark (Dashboard and VE calibration screen)."""
    window.show_screen(screen)

    window.keyPressEvent(key_press(Qt.Key.Key_Return))

    assert pressed == [int(Qt.Key.Key_Return)]


def test_key_signal_is_not_emitted_on_home(window, pressed):
    """Scenario: Home screen."""
    window.keyPressEvent(key_press(Qt.Key.Key_Down))
    window.keyPressEvent(key_press(Qt.Key.Key_Return))  # opens the VE screen

    assert pressed == []
    assert window._current_screen_name == "ve_calibration"


def test_enter_that_opens_a_screen_is_not_announced_after_the_switch(window, pressed):
    """Scenario: Home screen (the screen is judged before the key is handled)."""
    window.keyPressEvent(key_press(Qt.Key.Key_Return))  # Home -> Dashboard

    assert window._current_screen_name == "dashboard"
    assert pressed == []


def test_key_signal_ignores_auto_repeat(window, pressed):
    """Scenario: Held key."""
    window.show_screen("dashboard")

    window.keyPressEvent(key_press(Qt.Key.Key_Return))
    for _ in range(5):
        window.keyPressEvent(key_press(Qt.Key.Key_Return, auto_repeat=True))

    assert pressed == [int(Qt.Key.Key_Return)]


def test_key_signal_carries_every_key_so_listeners_can_filter(window, pressed):
    window.show_screen("ve_calibration")

    for key in (Qt.Key.Key_R, Qt.Key.Key_Enter, Qt.Key.Key_Up):
        window.keyPressEvent(key_press(key))

    assert pressed == [int(Qt.Key.Key_R), int(Qt.Key.Key_Enter), int(Qt.Key.Key_Up)]


def test_screen_still_handles_the_key_that_was_announced(window, pressed):
    window.show_screen("dashboard")

    window.keyPressEvent(key_press(Qt.Key.Key_Escape))

    assert pressed == [int(Qt.Key.Key_Escape)]
    assert window._current_screen_name == "home"


# ------------------------------------------------------------------ alarm onset

def test_alarm_onset_reaches_the_dashboard(window):
    """Requirement: Visual alarm flash (the window forwards the onset to the Dashboard)."""
    from app.masterinjection.signal import Signal

    window._screens["dashboard"].fire_field_alarm = Mock()

    window.on_alarm_onset(Signal.RPM)

    window._screens["dashboard"].fire_field_alarm.assert_called_once_with(Signal.RPM)


def test_real_alarm_processor_onset_flashes_the_dashboard_card(window, processor):
    """The wiring main() creates: alarm processor -> window -> Dashboard card."""
    from app.alarm.processor import AlarmProcessor
    from app.masterinjection.signal import Signal
    from tests.helpers import parsed

    alarm = AlarmProcessor("does-not-exist.wav")
    alarm.emitter.connect(window.on_alarm_onset)
    window._screens["dashboard"].fire_field_alarm = Mock()

    alarm.process_signals({Signal.RPM: parsed(Signal.RPM, 6700)})

    window._screens["dashboard"].fire_field_alarm.assert_called_once_with(Signal.RPM)


# ------------------------------------------------------------ connection errors

@pytest.mark.parametrize("screen", ["home", "dashboard", "ve_calibration"])
def test_connection_error_overlay_is_shown_on_every_screen(window, screen):
    """Requirement: Connection error overlay (visible on every screen)."""
    window.show_screen(screen)

    window.on_connection_error("Falha ao conectar em COM3")

    assert window._error_overlay.isVisible()
    assert window._current_screen_name == screen


def test_showing_the_overlay_does_not_change_the_active_screen(window):
    window.show_screen("ve_calibration")

    window.on_connection_error("erro")

    assert window.stacked_widget.currentWidget() is window._screens["ve_calibration"]


def test_keys_are_still_routed_to_the_active_screen_while_the_overlay_is_visible(window):
    """Scenario: Keys keep working."""
    window.on_connection_error("erro")

    window.keyPressEvent(key_press(Qt.Key.Key_Down))
    window.keyPressEvent(key_press(Qt.Key.Key_Return))  # Home: opens the VE calibration screen

    assert window._current_screen_name == "ve_calibration"
    assert window._error_overlay.isVisible()  # the keys neither dismissed it nor changed its timeout


def test_escape_still_navigates_while_the_overlay_is_visible(window):
    window.show_screen("dashboard")
    window.on_connection_error("erro")

    window.keyPressEvent(key_press(Qt.Key.Key_Escape))

    assert window._current_screen_name == "home"
    assert window._error_overlay.isVisible()


def test_a_second_error_replaces_the_message_in_the_same_overlay(window):
    from PyQt6.QtWidgets import QLabel

    window.on_connection_error("primeiro")
    window.on_connection_error("segundo")

    texts = [label.text() for label in window._error_overlay.findChildren(QLabel)]
    assert "segundo" in texts and "primeiro" not in texts


def test_the_thread_error_signal_reaches_the_overlay(window, qapp):
    """The wiring main() creates: connection thread error signal -> window -> overlay."""
    from app.ecu_connection.ecu_connection import EcuConnection
    from app.ecu_connection.thread import EcuConnectionThread

    class Silent(EcuConnection):
        def send_command(self, cmd, args=None): pass
        def run(self): pass
        def is_connected(self): return False

    connection = Silent()
    thread = EcuConnectionThread(connection)
    thread.error.connect(window.on_connection_error)

    connection.report_error("Conexão perdida: link lost")

    assert window._error_overlay.isVisible()
