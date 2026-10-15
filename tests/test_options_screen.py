"""Spec: openspec/specs/options-screen."""
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel

from app.masterinjection.protocol import EcuCommand, parse_x02
from app.state.state import vehicle_state
from app.ui.options.phase_write_controller import PhaseWriteController, STATUS_APPLIED, STATUS_NO_ANSWER
from app.ui.options.screen import OptionsScreen
from tests.helpers import key_press

NEGATIVE_LINE = "#X02;600;400;6;0;117;8000;6100;6300;5;2000;1750;0;1960;2;100;2"
POSITIVE_LINE = NEGATIVE_LINE.replace(";0;1960", ";1;1960")
PHASE_2_LINE = NEGATIVE_LINE.replace(";0;1960", ";2;1960")


@pytest.fixture
def options(qapp):
    sent = []
    holder = {}
    controller = PhaseWriteController(
        send_command=lambda cmd, args=None: sent.append((cmd, list(args) if args else None)),
        get_block=vehicle_state.get_x02,
        set_block=vehicle_state.set_x02,
        on_written=lambda: holder["screen"]._play_write_sound(),
    )
    screen = OptionsScreen(close_fn=Mock(), controller=controller)
    holder["screen"] = screen
    screen._player = Mock()
    screen.sent = sent
    screen.controller = controller
    return screen


def texts(screen):
    return [label.text() for label in screen.findChildren(QLabel)]


def phase_value(screen):
    return screen._field_rows[0][2].text()


def press(screen, key, auto_repeat=False):
    screen.keyPressEvent(key_press(key, auto_repeat))


# ---------------------------------------------------------------- layout

def test_initial_content(options):
    """Scenario: Initial content."""
    shown = texts(options)

    assert "Opções" in shown
    assert "Fase" in shown
    assert "↑↓ Navegar | Enter Alterar | Esc Voltar" in shown
    assert options._status_label.text() == ""
    assert "1E90FF" in options._field_rows[0][0].styleSheet()  # selected: blue border


# --------------------------------------------------------- phase display

def test_negative_phase_is_shown(options):
    """Scenario: Negative phase."""
    options.on_ecu_line(NEGATIVE_LINE)

    assert phase_value(options) == "Negativa"


def test_positive_phase_is_shown(options):
    """Scenario: Positive phase."""
    options.on_ecu_line(POSITIVE_LINE)

    assert phase_value(options) == "Positiva"


def test_unknown_phase_is_a_dash(options):
    """Scenario: Unknown phase."""
    assert phase_value(options) == "—"


def test_unexpected_phase_value_is_a_dash(options):
    """Scenario: Unexpected phase value."""
    options.on_ecu_line(PHASE_2_LINE)

    assert phase_value(options) == "—"


def test_field_follows_the_shared_state_without_a_key_press(options):
    """Requirement: Phase display (follows the shared state)."""
    vehicle_state.set_x02(parse_x02(POSITIVE_LINE))

    assert phase_value(options) == "Positiva"


# ---------------------------------------------------------------- toggle

def test_enter_toggles_to_the_requested_phase_and_marks_it_in_progress(options):
    """Scenarios: Toggle to positive / Change in progress."""
    options.on_ecu_line(NEGATIVE_LINE)

    press(options, Qt.Key.Key_Return)

    assert phase_value(options) == "Positiva …"
    assert options.controller._delay_timer.isActive()
    assert options._status_label.text() == "Alteração pendente…"


def test_keypad_enter_also_toggles(options):
    options.on_ecu_line(NEGATIVE_LINE)

    press(options, Qt.Key.Key_Enter)

    assert phase_value(options) == "Positiva …"


def test_toggling_twice_returns_to_the_original_phase(options):
    """Scenario: Toggle twice."""
    options.on_ecu_line(NEGATIVE_LINE)

    press(options, Qt.Key.Key_Return)
    press(options, Qt.Key.Key_Return)

    assert phase_value(options) == "Negativa …"


def test_enter_with_unknown_phase_does_nothing(options):
    """Scenario: Unknown phase (toggle)."""
    press(options, Qt.Key.Key_Return)

    assert phase_value(options) == "—"
    assert not options.controller._delay_timer.isActive()


def test_held_enter_toggles_once(options):
    """Scenario: Held key."""
    options.on_ecu_line(NEGATIVE_LINE)

    press(options, Qt.Key.Key_Return)
    press(options, Qt.Key.Key_Return, auto_repeat=True)
    press(options, Qt.Key.Key_Return, auto_repeat=True)

    assert phase_value(options) == "Positiva …"


def test_down_with_a_single_field_keeps_it_selected(options):
    """Scenario: Single field."""
    options.on_ecu_line(NEGATIVE_LINE)

    press(options, Qt.Key.Key_Down)
    press(options, Qt.Key.Key_Up)
    press(options, Qt.Key.Key_Return)

    assert phase_value(options) == "Positiva …"


def test_enter_on_options_is_not_announced_to_the_event_marker(qapp):
    """Scenario: No event mark (the window announces only data-screen presses)."""
    from app.ui.window import AppWindow
    assert "options" not in AppWindow._DATA_SCREENS


# -------------------------------------------------------------- status line

def test_whole_change_ends_with_the_success_message(options):
    """Scenario: Success message."""
    options.on_ecu_line(NEGATIVE_LINE)
    press(options, Qt.Key.Key_Return)
    options.controller._delay_timer.timeout.emit()
    options.on_ecu_line(NEGATIVE_LINE)
    options.on_ecu_line(POSITIVE_LINE)

    assert options._status_label.text() == STATUS_APPLIED
    assert phase_value(options) == "Positiva"


def test_failure_message_stays_until_the_next_toggle(options):
    """Scenario: Failure message kept."""
    options.on_ecu_line(NEGATIVE_LINE)
    press(options, Qt.Key.Key_Return)
    options.controller._delay_timer.timeout.emit()
    options.controller._answer_timer.timeout.emit()

    assert options._status_label.text() == STATUS_NO_ANSWER
    options.on_deactivated()
    assert options._status_label.text() == STATUS_NO_ANSWER

    press(options, Qt.Key.Key_Return)
    assert options._status_label.text() == "Alteração pendente…"


def test_success_message_goes_away_when_the_screen_is_left(options):
    """Requirement: Status messages (success stays until the screen is left)."""
    options.on_ecu_line(NEGATIVE_LINE)
    press(options, Qt.Key.Key_Return)
    options.controller._delay_timer.timeout.emit()
    options.on_ecu_line(NEGATIVE_LINE)
    options.on_ecu_line(POSITIVE_LINE)

    options.on_deactivated()

    assert options._status_label.text() == ""


# -------------------------------------------------------------- activation

def test_activation_queues_a_request_without_arguments(options):
    """Scenario: Open the screen."""
    options.on_activated()

    assert options.sent == [(EcuCommand.PARAMETERS_X02, None)]


def test_activation_during_a_change_queues_nothing(options):
    """Scenario: Open during a change."""
    options.on_ecu_line(NEGATIVE_LINE)
    press(options, Qt.Key.Key_Return)

    options.on_activated()

    assert options.sent == []


# ----------------------------------------------------------------- leaving

def test_escape_returns_to_home(options):
    """Scenario: Back to Home."""
    press(options, Qt.Key.Key_Escape)

    options.close_fn.assert_called_once()


def test_leaving_during_the_delay_does_not_cancel_the_write(options):
    """Scenario: Leave during the delay."""
    options.on_ecu_line(NEGATIVE_LINE)
    press(options, Qt.Key.Key_Return)

    options.on_deactivated()
    options.controller._delay_timer.timeout.emit()
    options.on_ecu_line(NEGATIVE_LINE)

    assert options.sent[-2:] == [(EcuCommand.PARAMETERS_X02, parse_x02(POSITIVE_LINE)),
                                 (EcuCommand.PARAMETERS_X02, None)]


# ------------------------------------------------------------------- sound

def test_write_restarts_the_ve_sound_even_after_leaving_the_screen(options):
    """Requirement: Write sound (Scenario: Screen left)."""
    options.on_ecu_line(NEGATIVE_LINE)
    press(options, Qt.Key.Key_Return)
    options.on_deactivated()
    options.controller._delay_timer.timeout.emit()
    options._player.play.assert_not_called()

    options.on_ecu_line(NEGATIVE_LINE)

    options._player.stop.assert_called_once()
    options._player.play.assert_called_once()
    assert not options._audio_output.isMuted()


def test_sound_uses_the_configured_ve_sound(qapp, monkeypatch):
    """Requirement: Write sound (configured ve_calibration.ve_sound)."""
    import app.ui.options.screen as options_module
    from types import SimpleNamespace
    monkeypatch.setattr(options_module, "config", SimpleNamespace(ve_calibration=SimpleNamespace(ve_sound="beep.wav")))

    screen = OptionsScreen(close_fn=Mock())

    assert screen._player.source().toLocalFile().endswith("beep.wav")
