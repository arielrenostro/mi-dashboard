"""Spec: openspec/specs/screen-navigation (full-screen window, lifecycle, key routing)."""
import csv
import os
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import Qt

from app.masterinjection.signal_processor import SignalProcessor
from app.ui.ignition_tuning.ignition_map_state import IgnitionMapState
from app.ui.ignition_tuning.results_log import IgnitionResultsLog
from app.ui.window import AppWindow
from tests.helpers import MAP_AXIS, SAMPLE_FRAME, ignition_set, key_press


@pytest.fixture
def processor():
    return SignalProcessor()


@pytest.fixture
def ecu_commands(monkeypatch):
    """Commands the Options screen queues; no real ECU connection exists in the tests."""
    import app.ui.options.screen as options_module
    sent = []
    monkeypatch.setattr(options_module, "get_ecu_connection",
                        lambda: Mock(send_command=lambda cmd, args=None: sent.append((cmd, args))))
    return sent


@pytest.fixture
def window(qapp, processor, ecu_commands):
    w = AppWindow(processor)
    yield w
    w.close()


def test_window_registers_the_six_screens_and_starts_on_home(window):
    """Requirement: Full-screen multi-screen window."""
    assert set(window._screens) == {"home", "dashboard", "ve_calibration", "ignition_tuning", "options", "settings"}
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


@pytest.mark.parametrize("screen", ["dashboard", "ve_calibration", "ignition_tuning", "options", "settings"])
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


def test_home_entry_shows_the_ignition_tuning_screen(window):
    """Scenario: Ignition tuning entry."""
    window.keyPressEvent(key_press(Qt.Key.Key_Down))
    window.keyPressEvent(key_press(Qt.Key.Key_Down))
    window.keyPressEvent(key_press(Qt.Key.Key_Return))

    assert window._current_screen_name == "ignition_tuning"
    assert window._screens["ignition_tuning"]._active


def test_escape_on_the_ignition_tuning_screen_returns_to_home(window):
    """Scenario: Back from ignition tuning."""
    window.show_screen("ignition_tuning")

    window.keyPressEvent(key_press(Qt.Key.Key_Escape))

    assert window._current_screen_name == "home"
    assert not window._screens["ignition_tuning"]._active


def test_telemetry_reaches_the_ignition_tuning_screen_only_while_it_is_active(window, processor):
    """Requirement: Live refresh (telemetry is analysed only while the screen is active)."""
    from tests.helpers import ignition_set

    calls = []
    window._screens["ignition_tuning"]._analysis.process = lambda *args: calls.append(args) or False

    processor.emitter.emit(ignition_set())
    assert calls == []

    window.show_screen("ignition_tuning")
    processor.emitter.emit(ignition_set())
    assert len(calls) == 1


def test_closing_the_window_writes_the_pending_ignition_results(window, processor, tmp_path):
    """Scenario: Ignition results are kept (app-lifecycle)."""
    screen = window._screens["ignition_tuning"]
    clock = [0.0]
    screen._clock = lambda: clock[0]
    screen._results = IgnitionResultsLog(screen._analysis, directory=str(tmp_path), clock=lambda: clock[0])
    screen._state = IgnitionMapState(max_map_kpa=70, ceiling=50)
    screen._state.load_breakpoints_map(MAP_AXIS)
    for row in range(16):
        screen._state.load_row(row, [20 + row + col for col in range(16)])
    window.show_screen("ignition_tuning")
    for _ in range(14):  # 5 s of settling after the loop closes, then four samples (the first one wrote the file)
        processor.emitter.emit(ignition_set())
        clock[0] += 0.5
    [name] = [f for f in os.listdir(tmp_path) if f.startswith("ignition_results_")]
    with open(tmp_path / name, newline="") as f:
        assert list(csv.reader(f, delimiter=";"))[1][5] == "1"

    window.close()

    with open(tmp_path / name, newline="") as f:
        assert list(csv.reader(f, delimiter=";"))[1][5] == "4"


def test_closing_the_window_without_ignition_results_is_harmless(window, tmp_path):
    window._screens["ignition_tuning"]._results = IgnitionResultsLog(
        window._screens["ignition_tuning"]._analysis, directory=str(tmp_path))

    window.close()

    assert os.listdir(tmp_path) == []


# ----------------------------------------------------------- global shortcuts

SHORTCUTS = [
    (Qt.Key.Key_F1, "dashboard"),
    (Qt.Key.Key_F2, "ve_calibration"),
    (Qt.Key.Key_F3, "ignition_tuning"),
    (Qt.Key.Key_F4, "options"),
    (Qt.Key.Key_F12, "settings"),
]


@pytest.mark.parametrize("origin", ["home", "dashboard", "ve_calibration", "ignition_tuning", "options", "settings"])
@pytest.mark.parametrize("key,target", SHORTCUTS)
def test_function_keys_open_their_screen_from_every_screen(window, origin, key, target):
    """Scenarios: F1 from Home / F2 from Dashboard / F3 from Options / F4 from VE calibration."""
    window.show_screen(origin)

    window.keyPressEvent(key_press(key))

    assert window._current_screen_name == target


def test_shortcut_of_the_visible_screen_does_nothing(window):
    """Scenario: Shortcut of the visible screen."""
    window.show_screen("dashboard")
    screen = window._screens["dashboard"]
    screen.on_activated = Mock()
    screen.on_deactivated = Mock()

    window.keyPressEvent(key_press(Qt.Key.Key_F1))

    screen.on_activated.assert_not_called()
    screen.on_deactivated.assert_not_called()
    assert window._current_screen_name == "dashboard"


def test_held_shortcut_switches_once(window):
    """Scenario: Held shortcut."""
    options = window._screens["options"]
    options.on_activated = Mock()

    window.keyPressEvent(key_press(Qt.Key.Key_F4))
    for _ in range(5):
        window.keyPressEvent(key_press(Qt.Key.Key_F4, auto_repeat=True))

    options.on_activated.assert_called_once()


def test_held_f12_shows_settings_once(window):
    """Scenario: Held shortcut (F12)."""
    settings = window._screens["settings"]
    settings.on_activated = Mock()

    window.keyPressEvent(key_press(Qt.Key.Key_F12))
    for _ in range(5):
        window.keyPressEvent(key_press(Qt.Key.Key_F12, auto_repeat=True))

    settings.on_activated.assert_called_once()


def test_auto_repeat_shortcut_alone_does_not_switch(window):
    window.keyPressEvent(key_press(Qt.Key.Key_F2, auto_repeat=True))

    assert window._current_screen_name == "home"


def test_shortcut_keys_are_not_delivered_to_any_screen(window):
    """Scenario: Shortcut key not delivered."""
    for screen in window._screens.values():
        screen.keyPressEvent = Mock()
        screen.keyReleaseEvent = Mock()
    window.show_screen("dashboard")

    for key, _ in SHORTCUTS:
        window.keyPressEvent(key_press(key))
        window.keyReleaseEvent(key_press(key))

    for screen in window._screens.values():
        screen.keyPressEvent.assert_not_called()
        screen.keyReleaseEvent.assert_not_called()


@pytest.mark.parametrize("screen", ["dashboard", "ve_calibration", "ignition_tuning"])
def test_shortcut_is_not_announced_as_a_key_event(window, pressed, screen):
    """Scenario: Shortcut not announced."""
    window.show_screen(screen)

    window.keyPressEvent(key_press(Qt.Key.Key_F1))

    assert pressed == []


def test_enter_on_options_is_not_announced(window, pressed):
    """Requirement: Phase toggle (no event mark on the Options screen)."""
    window.show_screen("options")
    window.keyPressEvent(key_press(Qt.Key.Key_Return))

    assert pressed == []


def test_enter_on_settings_is_not_announced(window, pressed):
    """Requirement: Keys and event marker (Settings is not a data screen)."""
    window.show_screen("settings")

    window.keyPressEvent(key_press(Qt.Key.Key_Return))
    window.keyPressEvent(key_press(Qt.Key.Key_Down))

    assert pressed == []


def test_a_setting_changed_on_the_settings_screen_reaches_the_ignition_screen(window):
    """Spec: a new RPM band is taken by the ignition analysis (wiring between the two screens)."""
    from app.config import config

    ignition = window._screens["ignition_tuning"]
    window.show_screen("settings")
    settings = window._screens["settings"]
    settings.keyPressEvent(key_press(Qt.Key.Key_Down))  # Conectar
    for _ in range(3):
        settings.keyPressEvent(key_press(Qt.Key.Key_Down))  # Zerar inclinação ... RPM mínimo
    settings.keyPressEvent(key_press(Qt.Key.Key_Down))  # RPM máximo
    assert settings.row_texts()[settings.selected_index][0] == "RPM máximo"

    settings.keyPressEvent(key_press(Qt.Key.Key_Right))

    assert config.ignition_tuning.rpm_max == 3200
    assert ignition._analysis.rpm_max == 3200


def test_opening_options_with_the_shortcut_requests_the_parameter_block(window, ecu_commands):
    """Requirement: Refresh on activation (through the window)."""
    from app.masterinjection.protocol import EcuCommand

    window.keyPressEvent(key_press(Qt.Key.Key_F4))

    assert ecu_commands == [(EcuCommand.PARAMETERS_X02, None)]


def test_x02_lines_reach_the_options_screen(window):
    """Wiring: the raw ECU lines are forwarded to the Options screen."""
    window.on_ecu_line("#X02;600;400;6;0;117;8000;6100;6300;5;2000;1750;1;1960;2;100;2")

    assert window._screens["options"]._field_rows[0][2].text() == "Positiva"
