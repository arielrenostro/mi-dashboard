"""Spec: openspec/specs/dashboard."""
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import Qt

from app.masterinjection.signal import Signal
from app.masterinjection.signal_processor import SignalProcessor
from app.ui.dashboard.screen import DashboardScreen
from tests.helpers import SAMPLE_FRAME, frame_with, key_press

GRID = [["RPM", "CLT", "GEAR"], ["BOOST", "LAMBDA", "POWER"]]
GRAPHS = [["RPM", "MAP"], ["LAMBDA", "LAMBDA_TARGET", "FUEL_TRIM"]]


@pytest.fixture
def dashboard(qapp):
    close = Mock()
    screen = DashboardScreen(close_fn=close, grid=GRID, graphs=GRAPHS, graph_x_size=5)
    screen.close = close
    return screen


def feed(screen, line=SAMPLE_FRAME):
    """Push a frame through the real signal processor into the screen."""
    processor = SignalProcessor()
    processor.emitter.connect(screen.on_signal_received)
    processor.process_line(line)


def value_text(screen, signal):
    return screen.labels[signal].big_label.text()


def value_style(screen, signal):
    return screen.labels[signal].big_label.styleSheet()


# ------------------------------------------------------------------------ grid

def test_grid_has_one_card_per_configured_signal_at_its_position(dashboard):
    """Requirement: Numeric grid."""
    for row, names in enumerate(GRID):
        for col, name in enumerate(names):
            assert dashboard.grid.itemAtPosition(row, col).widget() is dashboard.labels[Signal[name]]


def test_card_label_includes_unit_when_present(dashboard):
    """Scenario: Card with unit."""
    assert dashboard.labels[Signal.CLT].small_label.text() == "CLT (ºC)"


def test_card_label_has_no_parentheses_without_unit(dashboard):
    """Scenario: Card without unit."""
    assert dashboard.labels[Signal.GEAR].small_label.text() == "Gear"


def test_cards_show_placeholder_before_any_data(dashboard):
    """Scenario: No data yet."""
    assert all(card.big_label.text() == "--" for card in dashboard.labels.values())


def test_cards_start_in_the_signal_color(dashboard):
    assert "color:red;" in value_style(dashboard, Signal.RPM)
    assert "color:orange;" in value_style(dashboard, Signal.CLT)


def test_cards_update_with_each_frame(dashboard):
    """Scenario: New frame."""
    feed(dashboard)

    assert value_text(dashboard, Signal.RPM) == "3415"
    assert value_text(dashboard, Signal.CLT) == "87"
    assert value_text(dashboard, Signal.LAMBDA) == "1.12"
    assert value_text(dashboard, Signal.GEAR) == "4"

    feed(dashboard, frame_with({1: 4000}))

    assert value_text(dashboard, Signal.RPM) == "4000"


def test_cards_update_even_when_the_screen_is_not_active(dashboard):
    """Requirement: Live update (whether or not visible)."""
    assert not dashboard.timer.isActive()

    feed(dashboard)

    assert value_text(dashboard, Signal.RPM) == "3415"


def test_calculated_signal_is_displayed(dashboard):
    feed(dashboard)

    assert value_text(dashboard, Signal.POWER) != "--"


# ------------------------------------------------- out-of-limit color (as built)

def test_disabled_alarm_signal_above_its_limit_is_red(dashboard):
    """Scenario: Boost above its limit."""
    feed(dashboard, frame_with({3: 200}))  # BOOST limit 165, alarm disabled

    assert "color:red;" in value_style(dashboard, Signal.BOOST)


def test_signal_returns_to_its_color_when_back_within_limits(dashboard):
    """Scenario: Back within limits."""
    feed(dashboard, frame_with({3: 200}))
    feed(dashboard, frame_with({3: 150}))

    assert "color:blue;" in value_style(dashboard, Signal.BOOST)


# ----------------------------------------------------------------------- graphs

def test_one_curve_per_graphed_signal(dashboard):
    """Requirement: Graph groups."""
    assert set(dashboard.curves) == {Signal.RPM, Signal.MAP, Signal.LAMBDA, Signal.LAMBDA_TARGET, Signal.FUEL_TRIM}


def test_buffer_keeps_only_the_latest_samples(dashboard):
    """Scenario: Buffer full."""
    for rpm in range(1000, 1008):  # 8 frames, buffer size 5
        feed(dashboard, frame_with({1: rpm}))

    assert list(dashboard.buffers[Signal.RPM]) == [1003, 1004, 1005, 1006, 1007]


def test_buffers_fill_while_the_screen_is_hidden(dashboard):
    """Requirement: Graph data buffers."""
    feed(dashboard)

    assert list(dashboard.buffers[Signal.RPM]) == [3415]
    assert Signal.CLT not in dashboard.buffers  # only graphed signals are buffered


def test_graph_timer_runs_every_100ms_only_while_active(dashboard):
    assert not dashboard.timer.isActive()

    dashboard.on_activated()
    assert dashboard.timer.isActive() and dashboard.timer.interval() == 100

    dashboard.on_deactivated()
    assert not dashboard.timer.isActive()


def test_peak_and_minimum_markers_follow_the_buffer(dashboard):
    """Requirement: Peak and minimum markers."""
    for rpm in (3000, 5200, 1000, 4000):
        feed(dashboard, frame_with({1: rpm}))

    dashboard.update_graph()

    assert dashboard.peak_labels[Signal.RPM].toPlainText() == "5200 RPM"
    assert dashboard.min_labels[Signal.RPM].toPlainText() == "1000 RPM"
    assert dashboard.peak_markers[Signal.RPM].data["x"].tolist() == [1]  # first occurrence index of the maximum
    assert dashboard.min_markers[Signal.RPM].data["x"].tolist() == [2]


def test_marker_label_has_no_unit_text_when_unit_is_empty(qapp):
    screen = DashboardScreen(close_fn=Mock(), grid=[["GEAR"]], graphs=[["GEAR"]], graph_x_size=5)
    feed(screen)

    screen.update_graph()

    assert screen.peak_labels[Signal.GEAR].toPlainText() == "4"


def test_markers_and_labels_are_hidden_for_an_empty_buffer(dashboard):
    """Scenario: Empty buffer."""
    dashboard.update_graph()

    assert not dashboard.peak_markers[Signal.RPM].isVisible()
    assert not dashboard.peak_labels[Signal.RPM].isVisible()
    assert not dashboard.min_labels[Signal.RPM].isVisible()


def test_first_occurrence_is_used_when_extremes_repeat(dashboard):
    for rpm in (2000, 5000, 5000, 1000):
        feed(dashboard, frame_with({1: rpm}))

    dashboard.update_graph()

    assert dashboard.peak_markers[Signal.RPM].data["x"].tolist() == [1]


# ------------------------------------------------------------------------- keys

def test_escape_returns_to_home(dashboard):
    """Scenario: Back to Home."""
    dashboard.keyPressEvent(key_press(Qt.Key.Key_Escape))

    dashboard.close.assert_called_once()


@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_R, Qt.Key.Key_O])
def test_other_keys_do_nothing(dashboard, key):
    """Requirement: Dashboard keys."""
    dashboard.keyPressEvent(key_press(key))

    dashboard.close.assert_not_called()
