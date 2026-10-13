"""Spec: openspec/specs/ve-calibration-screen and openspec/specs/lambda-loop-control."""
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import Qt

import app.ui.ve_calibration.screen as screen_module
from app.masterinjection.protocol import EcuCommand
from app.masterinjection.signal import Signal
from app.state.state import vehicle_state
from app.ui.ve_calibration.screen import VeCalibrationScreen
from app.ui.ve_calibration.ve_map_state import ve_map_state
from tests.helpers import MAP_AXIS, RPM_AXIS, key_press, parsed

ROW, COL = 6, 4  # the node used as operating point in these tests


class RecordingConnection:
    def __init__(self):
        self.sent = []

    def send_command(self, cmd, args=None):
        self.sent.append((cmd, list(args or [])))


@pytest.fixture
def ve_screen(qapp, monkeypatch):
    ve_map_state.__init__()
    connection = RecordingConnection()
    monkeypatch.setattr(screen_module, "get_ecu_connection", lambda: connection)

    screen = VeCalibrationScreen(close_fn=Mock())
    screen.connection = connection
    screen._player_open, screen._player_closed = Mock(), Mock()
    screen.adjustments = []
    screen.ve_adjustment_made.connect(lambda: screen.adjustments.append(1))

    # The ECU publishes axes and rows to the shared state; the screen reacts to those events.
    vehicle_state.set_rpm_breakpoints(RPM_AXIS)
    vehicle_state.set_map_breakpoints(MAP_AXIS)
    for row in range(16):
        vehicle_state.set_ve_map([800 + row * 16 + col for col in range(16)], row)
    yield screen
    ve_map_state.__init__()


def set_operating_point(rpm=RPM_AXIS[COL], map_val=MAP_AXIS[ROW], **extra):
    data = {Signal.RPM: parsed(Signal.RPM, rpm), Signal.MAP: parsed(Signal.MAP, map_val)}
    data.update({Signal[k]: parsed(Signal[k], v) for k, v in extra.items()})
    vehicle_state.update(data)


def cell_text(screen, row, col):
    return screen.ve_table.item(15 - row, col).text()


# ---------------------------------------------------------------- keyboard edit

def test_up_increases_ve_by_five_raw_units_at_the_operating_point(ve_screen):
    """Scenario: Increase."""
    set_operating_point()
    before = ve_map_state.get_cell(ROW, COL)

    ve_screen.keyPressEvent(key_press(Qt.Key.Key_Up))

    assert ve_map_state.get_cell(ROW, COL) == before + 5


def test_down_decreases_ve_by_five_raw_units(ve_screen):
    set_operating_point()
    before = ve_map_state.get_cell(ROW, COL)

    ve_screen.keyPressEvent(key_press(Qt.Key.Key_Down))

    assert ve_map_state.get_cell(ROW, COL) == before - 5


def test_each_edit_signals_the_write_delay(ve_screen):
    set_operating_point()

    ve_screen.keyPressEvent(key_press(Qt.Key.Key_Up))
    ve_screen.keyPressEvent(key_press(Qt.Key.Key_Down))

    assert len(ve_screen.adjustments) == 2
    assert ve_screen._writer._timer.isActive()


def test_edit_is_ignored_without_an_operating_point(ve_screen):
    """Scenario: No operating point."""
    before = [row[:] for row in ve_map_state.ve_map]

    ve_screen.keyPressEvent(key_press(Qt.Key.Key_Up))

    assert ve_map_state.ve_map == before
    assert ve_screen.adjustments == []


def test_holding_a_key_repeats_the_edit(ve_screen):
    """Requirement: Keyboard editing (auto-repeat is not ignored)."""
    set_operating_point()
    before = ve_map_state.get_cell(ROW, COL)

    ve_screen.keyPressEvent(key_press(Qt.Key.Key_Up))
    ve_screen.keyPressEvent(key_press(Qt.Key.Key_Up, auto_repeat=True))
    ve_screen.keyPressEvent(key_press(Qt.Key.Key_Up, auto_repeat=True))

    assert ve_map_state.get_cell(ROW, COL) == before + 15


def test_reset_restores_the_map_and_schedules_a_write(ve_screen):
    """Scenario: Reset."""
    set_operating_point()
    original = ve_map_state.get_cell(ROW, COL)
    ve_screen.keyPressEvent(key_press(Qt.Key.Key_Up))

    ve_screen.keyPressEvent(key_press(Qt.Key.Key_R))

    assert ve_map_state.get_cell(ROW, COL) == original
    assert ve_map_state.get_pending_rows() == list(range(16))
    assert len(ve_screen.adjustments) == 2


def test_escape_returns_to_home(ve_screen):
    """Scenario: Leaving the screen / Return to Home with ESC."""
    ve_screen.keyPressEvent(key_press(Qt.Key.Key_Escape))

    ve_screen.close_fn.assert_called_once()


# ---------------------------------------------------------------- lambda loop

def test_o_opens_the_loop_and_plays_the_open_sound(ve_screen):
    """Scenario: Open."""
    ve_screen.keyPressEvent(key_press(Qt.Key.Key_O))

    assert ve_screen.connection.sent == [(EcuCommand.LAMBDA_LOOP_OPEN, [])]
    ve_screen._player_open.play.assert_called_once()
    ve_screen._player_closed.play.assert_not_called()


def test_p_closes_the_loop_and_plays_the_closed_sound(ve_screen):
    """Scenario: Close."""
    ve_screen.keyPressEvent(key_press(Qt.Key.Key_P))

    assert ve_screen.connection.sent == [(EcuCommand.LAMBDA_LOOP_CLOSE, [])]
    ve_screen._player_closed.play.assert_called_once()
    ve_screen._player_open.play.assert_not_called()


def test_loop_keys_do_not_change_any_displayed_state(ve_screen):
    """Requirement: Loop state comes from the ECU."""
    vehicle_state.update({Signal.LAMBDA_LOOP: parsed(Signal.LAMBDA_LOOP, 0)})

    ve_screen.keyPressEvent(key_press(Qt.Key.Key_P))

    assert vehicle_state.get(Signal.LAMBDA_LOOP).value == 0


# -------------------------------------------------------------------- top bar

def test_top_bar_has_the_seven_signals_in_order(ve_screen):
    """Requirement: Top bar."""
    assert list(ve_screen._top_bar_labels) == [
        Signal.RPM, Signal.MAP, Signal.VE, Signal.LAMBDA, Signal.LAMBDA_TARGET, Signal.FUEL_TRIM, Signal.LAMBDA_LOOP,
    ]


@pytest.mark.parametrize(
    "loop,color,text",
    [
        (0, "#FF8800", "Open"),  # scenario: Open loop
        (1, "#00FF00", "Closed"),
        (2, "#00FF00", "Closed+C"),  # scenario: Closed loop with correction
    ],
)
def test_lambda_loop_card_color_and_text(ve_screen, loop, color, text):
    """Requirement: Top bar (green for values 1 and 2, orange otherwise)."""
    vehicle_state.update({Signal.LAMBDA_LOOP: parsed(Signal.LAMBDA_LOOP, loop)})

    ve_screen._update_top_bar()

    card = ve_screen._top_bar_labels[Signal.LAMBDA_LOOP].big_label
    assert color in card.styleSheet()
    assert card.text() == text


def test_lambda_loop_card_turns_green_when_the_loop_closes(ve_screen):
    """Requirement: Top bar (color follows the ECU-reported value)."""
    card = ve_screen._top_bar_labels[Signal.LAMBDA_LOOP].big_label
    for loop, color in [(0, "#FF8800"), (2, "#00FF00"), (0, "#FF8800")]:
        vehicle_state.update({Signal.LAMBDA_LOOP: parsed(Signal.LAMBDA_LOOP, loop)})
        ve_screen._update_top_bar()
        assert color in card.styleSheet()


def test_top_bar_shows_display_strings(ve_screen):
    vehicle_state.update({
        Signal.RPM: parsed(Signal.RPM, 3415),
        Signal.LAMBDA: parsed(Signal.LAMBDA, 0.903),
        Signal.LAMBDA_LOOP: parsed(Signal.LAMBDA_LOOP, 0),
    })

    ve_screen._update_top_bar()

    assert ve_screen._top_bar_labels[Signal.RPM].big_label.text() == "3415"
    assert ve_screen._top_bar_labels[Signal.LAMBDA].big_label.text() == "0.90"
    assert ve_screen._top_bar_labels[Signal.LAMBDA_LOOP].big_label.text() == "Open"


# ------------------------------------------------------------ table and refresh

def test_refresh_cycle_does_nothing_without_an_operating_point(ve_screen):
    """Scenario: No data."""
    ve_screen._update_highlight()

    assert ve_screen._top_bar_labels[Signal.RPM].big_label.text() == "--"
    assert ve_screen._ve_signal_scatter.getData()[0] is None or len(ve_screen._ve_signal_scatter.getData()[0]) == 0


def test_refresh_cycle_shows_raw_values_with_highest_map_at_the_top(ve_screen):
    """Requirement: VE table."""
    set_operating_point()

    ve_screen._update_highlight()

    assert cell_text(ve_screen, 15, 0) == str(800 + 15 * 16)  # top-left = highest MAP, lowest RPM
    assert cell_text(ve_screen, 0, 15) == str(800 + 15)  # bottom-right = lowest MAP, highest RPM


def test_active_cells_are_tinted_orange_and_others_are_not(ve_screen):
    """Scenario: Active cells."""
    set_operating_point(rpm=(RPM_AXIS[COL] + RPM_AXIS[COL + 1]) / 2)

    ve_screen._update_highlight()
    active = ve_screen.ve_table.item(15 - ROW, COL).background().color().name()
    far = ve_screen.ve_table.item(15 - 0, 15).background().color().name()

    assert active != far
    assert ve_screen.ve_table.item(15 - ROW, COL + 1).background().color().name() == active  # equal weights


def test_modified_cell_text_is_cyan(ve_screen):
    """Scenario: Modified cell."""
    set_operating_point(rpm=RPM_AXIS[5], map_val=MAP_AXIS[ROW])
    ve_screen.keyPressEvent(key_press(Qt.Key.Key_Up))

    ve_screen._update_highlight()

    assert ve_screen.ve_table.item(15 - ROW, 5).foreground().color().name().upper() == "#00CCFF"
    assert ve_screen.ve_table.item(15 - ROW, 6).foreground().color().name().upper() == "#FFFFFF"


def test_axis_events_update_the_table_headers(ve_screen):
    """Scenario: Axes arrive late."""
    vehicle_state.set_rpm_breakpoints([100 * (i + 1) for i in range(16)])
    vehicle_state.set_map_breakpoints([10 * (i + 1) for i in range(16)])

    assert ve_screen.ve_table.horizontalHeaderItem(0).text() == "100"
    assert ve_screen.ve_table.horizontalHeaderItem(15).text() == "1600"
    assert ve_screen.ve_table.verticalHeaderItem(0).text() == "160"  # highest MAP on top
    assert ve_screen.ve_table.verticalHeaderItem(15).text() == "10"


def test_row_event_refreshes_that_table_row(ve_screen):
    """Scenario: Row arrives."""
    vehicle_state.set_ve_map([7000 + c for c in range(16)], 15)

    assert cell_text(ve_screen, 15, 0) == "7000"
    assert ve_map_state.original_ve_map[15][0] == 7000


def test_refresh_timer_runs_every_100ms_only_while_active(ve_screen):
    """Scenario: Leaving the screen."""
    ve_screen.on_activated()
    assert ve_screen._highlight_timer.isActive() and ve_screen._highlight_timer.interval() == 100

    ve_screen.on_deactivated()
    assert not ve_screen._highlight_timer.isActive()


# ------------------------------------------------------------------ VE graph

def test_graph_has_one_curve_per_map_row(ve_screen):
    """Requirement: VE graph."""
    assert len(ve_screen._ve_lines) == 16


def test_graph_curves_plot_ve_percent_against_the_rpm_axis(ve_screen):
    set_operating_point()

    ve_screen._update_highlight()
    x, y = ve_screen._ve_lines[3].getData()

    assert list(x) == RPM_AXIS
    assert list(y) == pytest.approx([(800 + 3 * 16 + c) / 10 for c in range(16)])


def test_ve_dot_follows_the_live_signals(ve_screen):
    set_operating_point(VE=62.7)

    ve_screen._update_highlight()
    x, y = ve_screen._ve_signal_scatter.getData()

    assert (list(x), list(y)) == ([RPM_AXIS[COL]], [62.7])


@pytest.mark.parametrize("loop,visible", [(0, False), (1, True), (2, True)])
def test_ve_lambda_dot_is_shown_only_in_closed_loop(ve_screen, loop, visible):
    """Scenarios: Closed loop / Open loop."""
    set_operating_point(VE_LAMBDA=55.0, LAMBDA_LOOP=loop)

    ve_screen._update_highlight()
    x, _ = ve_screen._ve_lambda_scatter.getData()

    assert (len(x) == 1) is visible
