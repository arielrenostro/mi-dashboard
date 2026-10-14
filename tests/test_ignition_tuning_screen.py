"""Spec: openspec/specs/ignition-tuning-screen (change ignition-tuning-screen)."""
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import Qt

import app.ui.ignition_tuning.ignition_write_controller as write_module
from app.masterinjection.protocol import EcuCommand
from app.state.state import vehicle_state
from app.ui.ignition_tuning.analysis import IgnitionAnalysis
from app.ui.ignition_tuning.ignition_map_state import IgnitionMapState
from app.ui.ignition_tuning.screen import (
    IgnitionTuningScreen, diff_color, format_column_offset, format_diff, format_offset, format_time,
)
from tests.helpers import MAP_AXIS, ignition_set, key_press

AFFECTED = 7  # MAP_AXIS 10..70 kPa are rows 0..6


def base_row(row):
    return [20 + row + col for col in range(16)]


class RecordingConnection:
    def __init__(self):
        self.sent = []

    def send_command(self, cmd, args=None):
        self.sent.append((cmd, list(args or [])))


class Env:
    """The screen with a fake clock, a recording ECU connection and mocked players."""

    def __init__(self, screen, connection, clock):
        self.screen = screen
        self.connection = connection
        self.clock = clock
        self.close = screen.close_fn

    @property
    def state(self):
        return self.screen._state

    def press(self, key, auto_repeat=False):
        self.screen.keyPressEvent(key_press(key, auto_repeat))

    def publish(self, **fields):
        data = ignition_set(**fields)
        vehicle_state.update(data)
        self.screen.on_signal_received(data)

    def feed(self, seconds, step=0.5, **fields):
        for _ in range(round(seconds / step)):
            self.publish(**fields)
            self.clock[0] += step

    def settle(self):
        """Closed-loop settling after the first set, so the next sets are samples."""
        self.feed(5.0)

    def write_now(self):
        """Let the 1 s write delay elapse."""
        self.screen._writer._timer.timeout.emit()

    def go_to(self, offset, **fields):
        """Press Up/Down until `offset`, write, wait for settling."""
        while self.state.offset != offset:
            self.press(Qt.Key.Key_Up if offset > self.state.offset else Qt.Key.Key_Down)
        self.write_now()
        self.feed(5.0, **fields)

    def columns(self):
        return self.screen._columns

    def texts(self, column_index, name):
        return self.columns()[column_index].labels[name].text()


@pytest.fixture
def env(qapp):
    connection = RecordingConnection()
    clock = [100.0]
    state = IgnitionMapState(max_map_kpa=70, ceiling=50)
    analysis = IgnitionAnalysis(rpm_min=2900, rpm_max=3100, gear=5, settle_seconds=5, min_scenario_seconds=20)

    write_module_original = write_module.get_ecu_connection
    write_module.get_ecu_connection = lambda: connection
    screen = IgnitionTuningScreen(close_fn=Mock(), state=state, analysis=analysis, clock=lambda: clock[0])
    screen._players = {name: Mock() for name in screen._players}
    screen._writer._player = Mock()
    # The ECU publishes the axis and the rows to the shared state; the screen reacts to those events.
    vehicle_state.set_map_breakpoints(MAP_AXIS)
    for row in range(16):
        vehicle_state.set_ignition_row(base_row(row), row)
    screen.on_activated()
    yield Env(screen, connection, clock)
    screen.on_deactivated()
    write_module.get_ecu_connection = write_module_original


@pytest.fixture
def unloaded(qapp):
    """A screen whose ECU data (axis and rows) never arrived."""
    connection = RecordingConnection()
    clock = [100.0]
    write_module_original = write_module.get_ecu_connection
    write_module.get_ecu_connection = lambda: connection
    screen = IgnitionTuningScreen(close_fn=Mock(), state=IgnitionMapState(max_map_kpa=70, ceiling=50),
                                  analysis=IgnitionAnalysis(2900, 3100, 5, 5, 20), clock=lambda: clock[0])
    screen._players = {name: Mock() for name in screen._players}
    screen._writer._player = Mock()
    screen.on_activated()
    yield Env(screen, connection, clock)
    screen.on_deactivated()
    write_module.get_ecu_connection = write_module_original


# ------------------------------------------------------------------------ formatting

def test_formatting_helpers():
    assert (format_offset(2), format_offset(0), format_offset(-1)) == ("+2°", "0°", "-1°")
    assert (format_column_offset(1), format_column_offset(0), format_column_offset(-1)) == ("+1°", "0° orig", "-1°")
    assert (format_time(0), format_time(38), format_time(70)) == ("00:00", "00:38", "01:10")
    assert (format_diff(None), format_diff(0.0), format_diff(0.04), format_diff(2.2), format_diff(-1.5)) == (
        "--", "0.0%", "0.0%", "+2.2%", "-1.5%")
    assert diff_color(0.0) == "#2ECC71"
    assert diff_color(1.0) != diff_color(6.0)


# ------------------------------------------------------------------------------ layout

def test_footer_lists_the_keys(env):
    """Scenario: Footer hints."""
    hint = env.screen.hint_label.text()

    for key in ("↑", "↓", "Espaço", "X", "R", "ESC"):
        assert key in hint


def test_top_bar_shows_the_live_values_and_the_offset(env):
    """Requirement: Top bar."""
    env.publish(rpm=3012, map=47, gear=5, ign=41)
    env.screen._refresh()

    cards = {signal.name: card.big_label.text() for signal, card in env.screen._top_bar_cards.items()}
    assert (cards["RPM"], cards["MAP"], cards["GEAR"], cards["IGN"]) == ("3012", "47", "5", "41")
    assert set(cards) == {"RPM", "MAP", "PEDAL", "GEAR", "IGN", "LAMBDA"}
    assert env.screen.offset_label.text() == "0°"


def test_values_never_received_show_dashes(env):
    env.screen._refresh()

    assert all(card.big_label.text() == "--" for card in env.screen._top_bar_cards.values())


# ------------------------------------------------------------------------------ status

def test_status_analysing(env):
    """Scenario: Analysing."""
    env.settle()
    env.feed(1.0)
    env.screen._refresh()

    assert env.screen.status_label.text() == "ANALISANDO"


def test_status_out_of_range(env):
    """Scenario: Out of range."""
    env.settle()
    env.publish(rpm=3400)
    env.screen._refresh()

    assert env.screen.status_label.text() == "FORA DA FAIXA"


def test_status_paused_has_priority(env):
    """Scenario: Paused has priority."""
    env.settle()
    env.press(Qt.Key.Key_Space)
    env.publish(rpm=3400)

    assert env.screen.status_label.text() == "PAUSADO"


def test_status_waits_for_the_ecu_when_the_map_is_not_loaded(unloaded):
    """Scenario: Map not loaded."""
    unloaded.publish()
    unloaded.screen._refresh()

    assert unloaded.screen.status_label.text() == "AGUARDANDO ECU"


def test_status_settling_after_the_loop_closes_again(env):
    """Scenario: Settling after the loop closes."""
    env.settle()
    env.publish(loop=0)
    env.clock[0] += 1.0
    env.publish(loop=1)
    env.screen._refresh()

    assert env.screen.status_label.text() == "ESTABILIZANDO"

    env.clock[0] += 5.0
    env.screen._refresh()
    assert env.screen.status_label.text() == "ANALISANDO"


# ------------------------------------------------------------------------------ columns

def test_empty_state_message_when_there_are_no_scenarios(env):
    """Scenario: Empty."""
    env.screen._refresh()

    assert env.columns() == []
    assert not env.screen.empty_label.isHidden()


def test_column_shows_the_scenario(env):
    """Scenario: Column content."""
    env.settle()
    env.go_to(+1, pulse=108, map=46, pedal=495)
    env.feed(39.5, pulse=108, map=46, pedal=495)  # 79 sets: 39 s of intervals
    env.screen._refresh()

    assert env.screen.empty_label.isHidden()
    column = [c for c in env.columns() if c.offset == 1][0]
    labels = {name: label.text() for name, label in column.labels.items()}
    assert labels["header"] == "+1°"
    assert labels["band"] == "2900-3100"
    assert labels["time"] == "00:39"
    assert labels["inj"] == "1.08 ms"
    assert labels["map"] == "46.0 kPa"
    assert labels["pedal"] == "50.0 %"
    assert labels["ign"].endswith("40.0")
    assert labels["knock"] == "Knock 0"


def test_columns_are_ordered_by_offset(env):
    """Scenario: Ordering."""
    env.settle()
    env.feed(1.0)
    env.go_to(+1)
    env.feed(1.0)
    env.go_to(-1)
    env.feed(1.0)
    env.screen._refresh()

    assert [c.labels["header"].text() for c in env.columns()] == ["-1°", "0° orig", "+1°"]


def test_ineligible_scenario_shows_dashes_for_the_percentages(env):
    """Scenario: Not eligible."""
    env.settle()
    env.feed(3.0)
    env.screen._refresh()

    column = env.columns()[0]
    assert [column.labels[n].text() for n in ("inj_diff", "map_diff", "pedal_diff")] == ["--", "--", "--"]


def test_eligible_scenarios_show_percentages_and_the_best_has_the_border(env):
    """Scenario: Best border."""
    env.settle()
    env.feed(21.0, pulse=110, map=47)
    env.go_to(+1, pulse=108, map=46)
    env.feed(21.0, pulse=108, map=46)
    env.screen._refresh()

    first, second = env.columns()
    assert (first.is_best, second.is_best) == (False, True)
    assert "#2ECC71" in second.styleSheet() and "#2ECC71" not in first.styleSheet()
    assert second.labels["inj_diff"].text() == "0.0%"
    assert first.labels["inj_diff"].text() == "+1.9%"
    assert first.labels["map_diff"].text() == "+2.2%"


def test_no_border_without_two_eligible_scenarios(env):
    """Scenario: No best."""
    env.settle()
    env.feed(21.0)
    env.screen._refresh()

    assert [c.is_best for c in env.columns()] == [False]


def test_current_offset_column_is_marked(env):
    env.settle()
    env.feed(2.0)
    env.go_to(+1)
    env.feed(2.0)
    env.screen._refresh()

    assert [c.is_current for c in env.columns()] == [False, True]


def test_columns_are_updated_in_place_when_nothing_new_appears(env):
    env.settle()
    env.feed(2.0)
    env.screen._refresh()
    column = env.columns()[0]

    env.feed(2.0)
    env.screen._refresh()

    assert env.columns()[0] is column


# ---------------------------------------------------------------------------------- keys

def test_up_raises_the_offset(env):
    """Scenario: Raise."""
    env.press(Qt.Key.Key_Up)

    assert env.state.offset == 1
    assert env.screen.offset_label.text() == "+1°"


def test_down_lowers_the_offset(env):
    env.press(Qt.Key.Key_Down)

    assert env.state.offset == -1
    assert env.screen.offset_label.text() == "-1°"


@pytest.mark.parametrize("key", [Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Space, Qt.Key.Key_X, Qt.Key.Key_R,
                                 Qt.Key.Key_Escape])
def test_held_keys_act_only_once(env, key):
    """Scenario: Held key."""
    env.press(key, auto_repeat=True)

    assert env.state.offset == 0
    assert not env.screen._analysis.paused
    env.close.assert_not_called()
    assert env.screen._writer._timer.isActive() is False


def test_holding_up_changes_the_offset_once(env):
    env.press(Qt.Key.Key_Up)
    env.press(Qt.Key.Key_Up, auto_repeat=True)
    env.press(Qt.Key.Key_Up, auto_repeat=True)

    assert env.state.offset == 1


def test_up_does_nothing_while_the_map_is_not_loaded(unloaded):
    """Scenario: Map not loaded."""
    unloaded.press(Qt.Key.Key_Up)
    unloaded.write_now()

    assert unloaded.state.offset == 0
    assert unloaded.connection.sent == []
    assert not unloaded.screen._writer._timer.isActive()


def test_space_toggles_the_pause(env):
    """Scenario: Pause toggle."""
    env.press(Qt.Key.Key_Space)
    assert env.screen._analysis.paused

    env.press(Qt.Key.Key_Space)
    assert not env.screen._analysis.paused


def test_reset_restores_everything_and_writes_all_rows(env):
    """Scenario: Reset."""
    env.settle()
    env.go_to(+3)
    env.feed(2.0)
    env.press(Qt.Key.Key_Space)
    env.connection.sent.clear()

    env.press(Qt.Key.Key_R)

    assert env.state.offset == 0
    assert env.screen._analysis.scenarios() == []
    assert not env.screen._analysis.paused
    assert env.screen._writer._timer.isActive()
    env.write_now()
    assert [cmd for cmd, _ in env.connection.sent] == [EcuCommand[f"IGN_ROW_{n}"] for n in range(1, 17)]
    assert env.connection.sent[2][1] == base_row(2)


def three_eligible_scenarios(env, pulses=(112, 110, 108)):
    """Eligible scenarios at offsets 0, +1, +2 with the given injection pulses; the current offset is +2."""
    env.settle()
    env.feed(21.0, pulse=pulses[0])
    for offset, pulse in enumerate(pulses[1:], start=1):
        env.go_to(offset, pulse=pulse)
        env.feed(21.0, pulse=pulse)
    env.screen._refresh()


def test_x_discards_the_worst_scenario_without_touching_the_map(env):
    """Scenario: Discard the worst."""
    three_eligible_scenarios(env)
    env.screen._writer._timer.stop()  # the helper only simulated the 1 s delay elapsing
    env.connection.sent.clear()
    pending_before = env.state.get_pending_rows()

    env.press(Qt.Key.Key_X)

    assert [c.offset for c in env.columns()] == [1, 2]
    assert env.state.offset == 2
    assert env.state.get_pending_rows() == pending_before == []
    assert not env.screen._writer._timer.isActive()
    env.write_now()
    assert env.connection.sent == []


def test_x_changes_nothing_when_the_worst_is_the_current_scenario(env):
    """Scenario: Worst is the current one."""
    three_eligible_scenarios(env, pulses=(108, 110, 112))

    env.press(Qt.Key.Key_X)

    assert [c.offset for c in env.columns()] == [0, 1, 2]


def test_x_changes_nothing_when_fewer_than_two_scenarios_are_eligible(env):
    """Scenario: Nothing to compare."""
    env.settle()
    env.feed(21.0)
    env.go_to(+1)
    env.feed(5.0)  # the second scenario is too short
    env.screen._refresh()

    env.press(Qt.Key.Key_X)

    assert [c.offset for c in env.columns()] == [0, 1]


def test_x_without_any_scenario_does_nothing(env):
    env.press(Qt.Key.Key_X)

    assert env.columns() == []
    env.screen._players["discard"].play.assert_not_called()


def test_escape_returns_to_home(env):
    """Scenario: Back to Home."""
    env.press(Qt.Key.Key_Escape)

    env.close.assert_called_once()


def test_other_keys_change_nothing(env):
    for key in (Qt.Key.Key_A, Qt.Key.Key_Return, Qt.Key.Key_Left):
        env.press(key)

    assert env.state.offset == 0
    assert not env.screen._analysis.paused
    env.close.assert_not_called()
    assert not env.screen._writer._timer.isActive()


# ------------------------------------------------------------------- hidden / refresh

def test_state_is_kept_while_the_screen_is_hidden(env):
    """Scenario: Leave and return."""
    env.settle()
    env.go_to(+2)
    env.feed(3.0)
    before = [(s.offset, s.samples) for s in env.screen._analysis.scenarios()]

    env.screen.on_deactivated()
    env.screen.on_activated()

    assert env.state.offset == 2
    assert [(s.offset, s.samples) for s in env.screen._analysis.scenarios()] == before


def test_telemetry_is_not_analysed_while_hidden(env):
    """Scenario: Hidden."""
    env.settle()
    env.feed(2.0)
    before = env.screen._analysis.scenarios()[0].samples
    env.screen.on_deactivated()

    env.feed(10.0)

    assert env.screen._analysis.scenarios()[0].samples == before


def test_refresh_runs_every_100_ms_while_active_and_stops_when_hidden(env):
    """Scenario: Refresh stops when hidden."""
    assert env.screen._refresh_timer.isActive()
    assert env.screen._refresh_timer.interval() == 100

    env.screen.on_deactivated()

    assert not env.screen._refresh_timer.isActive()


# ----------------------------------------------------------------------- ECU data in

def test_axis_and_rows_published_to_the_shared_state_reach_the_model(env):
    assert env.state.is_loaded()
    assert env.state.map_axis == MAP_AXIS
    assert env.state.original[3] == base_row(3)


# ---------------------------------------------------------------------------- write

def test_burst_of_presses_makes_a_single_write_with_the_final_offset(env):
    """Scenario: Burst."""
    for _ in range(3):
        env.press(Qt.Key.Key_Up)

    assert env.screen._writer._timer.isActive()
    assert env.screen._writer._timer.interval() == 1000
    assert env.connection.sent == []

    env.write_now()

    assert len(env.connection.sent) == AFFECTED
    assert env.connection.sent[0][1] == [v + 3 for v in base_row(0)]


def test_rows_are_written_in_order_with_sixteen_values(env):
    """Scenario: Rows written."""
    env.press(Qt.Key.Key_Up)
    env.write_now()

    assert [cmd for cmd, _ in env.connection.sent] == [EcuCommand[f"IGN_ROW_{n}"] for n in range(1, 8)]
    assert all(len(values) == 16 for _, values in env.connection.sent)
    cmd, values = env.connection.sent[5]
    assert f"{cmd.cmd};" + ";".join(map(str, values)) == "#I06;" + ";".join(str(v + 1) for v in base_row(5))


def test_rows_above_the_limit_are_never_written(env):
    env.press(Qt.Key.Key_Up)
    env.press(Qt.Key.Key_Up)
    env.write_now()

    assert EcuCommand.IGN_ROW_8 not in [cmd for cmd, _ in env.connection.sent]


def test_an_offset_raised_and_lowered_within_the_delay_sends_nothing(env):
    """Scenario: Not written."""
    env.press(Qt.Key.Key_Up)
    env.press(Qt.Key.Key_Down)
    env.write_now()

    assert env.connection.sent == []
    env.screen._writer._player.play.assert_not_called()


def test_write_on_memory_is_never_sent(env):
    """Scenario: No persistence."""
    env.press(Qt.Key.Key_Up)
    env.write_now()
    env.press(Qt.Key.Key_R)
    env.write_now()

    assert EcuCommand.WRITE_ON_MEMORY not in [cmd for cmd, _ in env.connection.sent]


def test_the_analysis_starts_settling_when_the_write_runs(env):
    env.settle()
    env.press(Qt.Key.Key_Up)
    env.feed(3.0)  # still waiting for the write
    assert env.screen._analysis.scenarios() == []

    env.write_now()
    env.feed(4.5)
    assert env.screen._analysis.scenarios() == []

    env.feed(1.0)
    assert env.screen._analysis.scenarios()[0].offset == 1


# ---------------------------------------------------------------------------- sounds

def test_write_sound_plays_once_when_rows_are_queued(env):
    """Scenario: Write sound."""
    env.press(Qt.Key.Key_Up)
    env.write_now()

    env.screen._writer._player.stop.assert_called_once()
    env.screen._writer._player.play.assert_called_once()


def test_ready_sound_plays_once_when_the_scenario_has_enough_time(env):
    """Scenario: Ready sound."""
    env.settle()
    env.feed(19.0, step=1.0)
    env.screen._players["ready"].play.assert_not_called()

    env.feed(3.0, step=1.0)

    env.screen._players["ready"].play.assert_called_once()


def test_discard_sound_plays_once_when_a_scenario_is_discarded(env):
    """Scenario: Discard sound."""
    three_eligible_scenarios(env)

    env.press(Qt.Key.Key_X)

    env.screen._players["discard"].stop.assert_called_once()
    env.screen._players["discard"].play.assert_called_once()


def test_no_sound_when_nothing_is_discarded(env):
    """Scenario: Nothing discarded."""
    three_eligible_scenarios(env, pulses=(108, 110, 112))

    env.press(Qt.Key.Key_X)

    env.screen._players["discard"].play.assert_not_called()


def test_pause_and_resume_sounds(env):
    """Scenario: Pause and resume sounds."""
    env.press(Qt.Key.Key_Space)
    env.screen._players["pause"].play.assert_called_once()
    env.screen._players["resume"].play.assert_not_called()

    env.press(Qt.Key.Key_Space)

    env.screen._players["resume"].play.assert_called_once()
    env.screen._players["pause"].play.assert_called_once()


def test_the_write_beep_is_muted_while_the_screen_is_hidden(env):
    """Requirement: Audible cues (only while the screen is active)."""
    env.screen.on_deactivated()
    assert env.screen._writer._audio_output.isMuted()

    env.screen.on_activated()

    assert not env.screen._writer._audio_output.isMuted()
