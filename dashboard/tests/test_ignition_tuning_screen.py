"""Spec: openspec/specs/ignition-tuning-screen (changes ignition-tuning-screen and ignition-multi-gear)."""
import csv
import os
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import Qt

import app.ui.ignition_tuning.ignition_write_controller as write_module
from app.config import config
from app.gyro.state import GyroSnapshot, GyroStatus
from app.masterinjection.protocol import EcuCommand
from app.masterinjection.signal import Signal
from app.masterinjection.signal_processor import SignalProcessor
from app.state.state import vehicle_state
from app.ui.ignition_tuning.analysis import IgnitionAnalysis
from app.ui.ignition_tuning.ignition_map_state import IgnitionMapState
from app.ui.ignition_tuning.results_log import IgnitionResultsLog
from app.ui.ignition_tuning.screen import (
    IgnitionTuningScreen, diff_color, format_column_offset, format_diff, format_offset, format_time,
)
from tests.helpers import MAP_AXIS, frame_with, ignition_set, key_press

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

    def __init__(self, screen, connection, clock, results_dir=None):
        self.screen = screen
        self.results_dir = results_dir
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


def make_screen(clock, tmp_path, gears, state=None, gyro=None):
    """A screen whose results go to `tmp_path` and whose clock is `clock[0]`."""
    state = IgnitionMapState(max_map_kpa=70, ceiling=50) if state is None else state
    analysis = IgnitionAnalysis(rpm_min=2900, rpm_max=3100, gears=gears, settle_seconds=5, min_scenario_seconds=20)
    wall = datetime(2026, 10, 15, 14, 0, 0)
    results = IgnitionResultsLog(analysis, directory=str(tmp_path), clock=lambda: clock[0],
                                 wall_clock=lambda: wall + timedelta(seconds=clock[0]))
    return IgnitionTuningScreen(close_fn=Mock(), state=state, analysis=analysis, clock=lambda: clock[0],
                                results=results, gyro=gyro)


@pytest.fixture
def env(qapp, tmp_path):
    connection = RecordingConnection()
    clock = [100.0]

    write_module_original = write_module.get_ecu_connection
    write_module.get_ecu_connection = lambda: connection
    screen = make_screen(clock, tmp_path, [5])
    screen._players = {name: Mock() for name in screen._players}
    screen._writer._player = Mock()
    # The ECU publishes the axis and the rows to the shared state; the screen reacts to those events.
    vehicle_state.set_map_breakpoints(MAP_AXIS)
    for row in range(16):
        vehicle_state.set_ignition_row(base_row(row), row)
    screen.on_activated()
    yield Env(screen, connection, clock, tmp_path)
    screen.on_deactivated()
    write_module.get_ecu_connection = write_module_original


@pytest.fixture
def two_gears(qapp, tmp_path):
    """A screen analysing 4th and 5th gear."""
    connection = RecordingConnection()
    clock = [100.0]
    write_module_original = write_module.get_ecu_connection
    write_module.get_ecu_connection = lambda: connection
    screen = make_screen(clock, tmp_path, [4, 5])
    screen._players = {name: Mock() for name in screen._players}
    screen._writer._player = Mock()
    vehicle_state.set_map_breakpoints(MAP_AXIS)
    for row in range(16):
        vehicle_state.set_ignition_row(base_row(row), row)
    screen.on_activated()
    yield Env(screen, connection, clock, tmp_path)
    screen.on_deactivated()
    write_module.get_ecu_connection = write_module_original


@pytest.fixture
def unloaded(qapp, tmp_path):
    """A screen whose ECU data (axis and rows) never arrived."""
    connection = RecordingConnection()
    clock = [100.0]
    write_module_original = write_module.get_ecu_connection
    write_module.get_ecu_connection = lambda: connection
    screen = make_screen(clock, tmp_path, [5])
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

    for key in ("↑", "↓", "←→", "Espaço", "X", "R", "G", "ESC"):
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
    assert "band" not in labels
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
    assert env.screen._analysis.scenarios(5) == []
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
    before = [(s.offset, s.samples) for s in env.screen._analysis.scenarios(5)]

    env.screen.on_deactivated()
    env.screen.on_activated()

    assert env.state.offset == 2
    assert [(s.offset, s.samples) for s in env.screen._analysis.scenarios(5)] == before


def test_telemetry_is_not_analysed_while_hidden(env):
    """Scenario: Hidden."""
    env.settle()
    env.feed(2.0)
    before = env.screen._analysis.scenarios(5)[0].samples
    env.screen.on_deactivated()

    env.feed(10.0)

    assert env.screen._analysis.scenarios(5)[0].samples == before


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
    assert env.screen._analysis.scenarios(5) == []

    env.write_now()
    env.feed(4.5)
    assert env.screen._analysis.scenarios(5) == []

    env.feed(1.0)
    assert env.screen._analysis.scenarios(5)[0].offset == 1


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


# ------------------------------------------------- several gears (ignition-multi-gear)

def temperatures(clt_raw, iat_raw):
    """Publish a frame with the given raw CLT and IAT (both are the value plus 273)."""
    processor = SignalProcessor()
    received = []
    processor.emitter.connect(received.append)
    processor.process_line(frame_with({19: clt_raw, 20: iat_raw}))
    vehicle_state.update(received[0])


def eligible_in(env, gear, pulse, seconds=21.0):
    env.feed(seconds, gear=gear, pulse=pulse)


def test_the_second_line_shows_coolant_and_intake_temperature(env):
    """Scenario: Coolant and intake temperature."""
    temperatures(360, 314)
    env.screen._refresh()

    cards = env.screen._second_line_cards
    assert (cards[Signal.CLT].big_label.text(), cards[Signal.IAT].big_label.text()) == ("87", "41")


def test_temperatures_never_received_show_dashes(env):
    """Scenario: Temperatures never received."""
    env.screen._refresh()

    assert [c.big_label.text() for c in env.screen._second_line_cards.values()] == ["--", "--"]


def test_the_second_line_shows_the_analysed_rpm_band(env):
    """Scenario: Analysed RPM band."""
    env.screen._refresh()

    assert env.screen.band_label.text() == "Faixa 2900-3100"


def test_the_gear_indicator_marks_the_shown_gear_and_the_gears_with_data(two_gears):
    """Scenario: Gear indicator."""
    two_gears.screen._refresh()
    assert two_gears.screen.gear_label.text() == "4ª  [5ª]"

    two_gears.settle()
    two_gears.feed(2.0, gear=4)
    two_gears.press(Qt.Key.Key_Right)

    assert two_gears.screen.gear_label.text() == "4ª•  [5ª]"


def test_the_shown_gear_has_the_dot_inside_the_brackets(two_gears):
    """Scenario: Shown gear with data."""
    two_gears.settle()
    two_gears.feed(2.0, gear=5)
    two_gears.feed(2.0, gear=4)
    two_gears.press(Qt.Key.Key_Right)

    assert two_gears.screen.gear_label.text() == "4ª•  [5ª•]"


def test_a_single_configured_gear_is_still_shown(env):
    """Scenario: Single configured gear."""
    env.screen._refresh()

    assert env.screen.gear_label.text() == "[5ª]"


def test_the_columns_show_only_the_shown_gear(two_gears):
    """Scenario: Only the shown gear."""
    two_gears.settle()
    two_gears.feed(2.0, gear=4)
    two_gears.go_to(+1, gear=4)
    two_gears.feed(2.0, gear=4)
    two_gears.feed(2.0, gear=5)  # offset +1 in gear 5; gear 5 is shown now
    two_gears.screen._refresh()

    assert [c.offset for c in two_gears.columns()] == [1]


def test_a_gear_without_scenarios_shows_the_empty_message(two_gears):
    """Scenario: Empty gear."""
    two_gears.settle()
    two_gears.feed(2.0, gear=4)
    two_gears.press(Qt.Key.Key_Right)

    assert two_gears.screen._shown_gear == 5
    assert two_gears.columns() == []
    assert not two_gears.screen.empty_label.isHidden()


def test_the_best_border_belongs_to_the_shown_gear(two_gears):
    """Scenario: Best of the other gear."""
    two_gears.settle()
    eligible_in(two_gears, 4, 120)
    two_gears.go_to(+1, gear=4, pulse=118)
    eligible_in(two_gears, 4, 118)
    two_gears.press(Qt.Key.Key_Left)  # nothing: already on the lowest gear
    two_gears.feed(1.0, gear=5, pulse=108)
    two_gears.screen._refresh()

    assert two_gears.screen._shown_gear == 5
    assert [c.is_best for c in two_gears.columns()] == [False]
    two_gears.press(Qt.Key.Key_Left)
    assert [c.is_best for c in two_gears.columns()] == [False, True]


def test_the_initial_shown_gear_is_the_highest_configured_one(two_gears):
    """Scenario: Initial gear."""
    assert two_gears.screen._shown_gear == 5


def test_the_shown_gear_follows_the_engaged_gear(two_gears):
    """Scenario: Follows the engaged gear."""
    two_gears.settle()
    two_gears.feed(1.0, gear=5)

    two_gears.feed(1.0, gear=4)

    assert two_gears.screen._shown_gear == 4


@pytest.mark.parametrize("gear", [3, 0])
def test_a_gear_that_is_not_configured_keeps_the_shown_gear(two_gears, gear):
    """Scenario: Not a configured gear."""
    two_gears.settle()
    two_gears.feed(1.0, gear=4)

    two_gears.feed(1.0, gear=gear)

    assert two_gears.screen._shown_gear == 4


def test_left_and_right_change_the_shown_gear_only(two_gears):
    """Scenario: Manual change."""
    two_gears.settle()
    two_gears.go_to(+1)
    two_gears.feed(2.0, gear=5)
    before = [(s.offset, s.samples) for s in two_gears.screen._analysis.scenarios(5)]
    two_gears.screen._writer._timer.stop()  # the helper only simulated the 1 s delay elapsing
    two_gears.connection.sent.clear()

    two_gears.press(Qt.Key.Key_Left)

    assert two_gears.screen._shown_gear == 4
    assert two_gears.state.offset == 1
    assert [(s.offset, s.samples) for s in two_gears.screen._analysis.scenarios(5)] == before
    assert not two_gears.screen._writer._timer.isActive()
    assert two_gears.connection.sent == []


def test_a_manual_choice_lasts_until_the_engaged_gear_changes(two_gears):
    """Scenario: Manual choice kept."""
    two_gears.settle()
    two_gears.feed(1.0, gear=5)
    two_gears.press(Qt.Key.Key_Left)

    two_gears.feed(3.0, gear=5)
    assert two_gears.screen._shown_gear == 4

    two_gears.feed(1.0, gear=4)
    two_gears.feed(1.0, gear=5)
    assert two_gears.screen._shown_gear == 5


def test_the_gear_list_does_not_wrap(two_gears):
    """Scenario: End of the list."""
    two_gears.press(Qt.Key.Key_Right)
    assert two_gears.screen._shown_gear == 5

    two_gears.press(Qt.Key.Key_Left)
    two_gears.press(Qt.Key.Key_Left)
    assert two_gears.screen._shown_gear == 4


def test_left_and_right_do_nothing_with_a_single_gear(env):
    """Scenario: Single gear."""
    env.press(Qt.Key.Key_Left)
    env.press(Qt.Key.Key_Right)

    assert env.screen._shown_gear == 5


def test_a_held_arrow_acts_once(two_gears):
    two_gears.press(Qt.Key.Key_Left, auto_repeat=True)

    assert two_gears.screen._shown_gear == 5


def test_sampling_goes_on_in_the_engaged_gear_while_another_is_shown(two_gears):
    """Scenario: Sampling is independent of the display."""
    two_gears.settle()
    two_gears.feed(2.0, gear=4)
    two_gears.feed(1.0, gear=5)
    two_gears.press(Qt.Key.Key_Left)
    two_gears.screen._refresh()
    shown_time = two_gears.texts(0, "time")
    samples = two_gears.screen._analysis.scenarios(5)[0].samples

    two_gears.feed(6.0, gear=5)

    assert two_gears.screen._analysis.scenarios(5)[0].samples > samples
    assert two_gears.texts(0, "time") == shown_time


def test_x_discards_only_in_the_shown_gear(two_gears):
    """Scenario: Discard only in the shown gear."""
    two_gears.settle()
    eligible_in(two_gears, 5, 112)
    two_gears.go_to(+1, gear=5, pulse=110)
    eligible_in(two_gears, 5, 110)
    two_gears.go_to(+2, gear=5, pulse=108)
    eligible_in(two_gears, 5, 108)
    eligible_in(two_gears, 4, 130)  # gear 4 at +2: shown while engaged
    two_gears.press(Qt.Key.Key_Right)
    assert two_gears.screen._shown_gear == 5

    two_gears.press(Qt.Key.Key_X)

    assert [s.offset for s in two_gears.screen._analysis.scenarios(5)] == [1, 2]
    assert [s.offset for s in two_gears.screen._analysis.scenarios(4)] == [2]


def test_reset_clears_the_scenarios_of_every_gear(two_gears):
    """Scenario: Reset."""
    two_gears.settle()
    two_gears.go_to(+3)
    two_gears.feed(2.0, gear=5)
    two_gears.feed(2.0, gear=4)

    two_gears.press(Qt.Key.Key_R)

    assert two_gears.state.offset == 0
    assert two_gears.screen._analysis.gears_with_data() == []
    two_gears.screen._refresh()
    assert two_gears.columns() == []


# -------------------------------------------------------------------- results file

def result_files(env):
    return sorted(f for f in os.listdir(env.results_dir) if f.startswith("ignition_results_"))


def result_rows(env, name):
    with open(os.path.join(env.results_dir, name), newline="") as f:
        return list(csv.reader(f, delimiter=";"))[1:]


def test_an_accepted_sample_creates_the_results_file(env):
    env.settle()
    assert result_files(env) == []

    env.feed(1.0)

    assert len(result_files(env)) == 1


def test_leaving_the_screen_writes_the_pending_results(env):
    env.settle()
    env.feed(3.0)  # the first sample wrote the file; the rest is inside the interval

    env.screen.on_deactivated()

    [name] = result_files(env)
    assert result_rows(env, name)[0][5] == "6"


def test_a_reset_closes_the_file_and_the_next_run_opens_another(env):
    env.settle()
    env.feed(3.0)

    env.press(Qt.Key.Key_R)
    env.write_now()
    env.settle()
    env.feed(1.0)

    names = result_files(env)
    assert len(names) == 2
    assert result_rows(env, names[0])[0][5] == "6"


def test_a_discarded_scenario_stays_in_the_file(env):
    three_eligible_scenarios(env)

    env.press(Qt.Key.Key_X)
    env.screen.on_deactivated()

    [name] = result_files(env)
    assert [(row[1], row[17]) for row in result_rows(env, name)] == [("0", "1"), ("1", "0"), ("2", "0")]


def test_an_unusable_results_directory_does_not_stop_the_analysis(env, tmp_path):
    env.screen._results._directory = str(tmp_path / "missing")
    env.settle()

    env.feed(3.0)
    env.screen.on_deactivated()

    assert env.screen._analysis.scenarios(5)[0].samples == 6
    assert result_files(env) == []


# ------------------------------------------------------------------ inclinometer (gyro-inclination)

class FakeGyro:
    """The inclinometer as the screen sees it."""

    def __init__(self, status=GyroStatus.DISABLED, pitch=None):
        self.status = status
        self.pitch = pitch
        self.zero_calls = 0

    def snapshot(self):
        return GyroSnapshot(self.status, self.pitch if self.status is GyroStatus.USABLE else None, None, "")

    def zero(self):
        self.zero_calls += 1
        return self.status not in (GyroStatus.DISABLED, GyroStatus.DISCONNECTED)

    def use(self, pitch):
        self.status, self.pitch = GyroStatus.USABLE, pitch


@pytest.fixture
def tilt_env(qapp, tmp_path):
    """The screen with a configured inclinometer (usable, level) and a settled analysis."""
    connection = RecordingConnection()
    clock = [100.0]
    gyro = FakeGyro(GyroStatus.USABLE, 0.5)
    write_module_original = write_module.get_ecu_connection
    write_module.get_ecu_connection = lambda: connection
    screen = make_screen(clock, tmp_path, [5], gyro=gyro)
    screen._players = {name: Mock() for name in screen._players}
    screen._writer._player = Mock()
    vehicle_state.set_map_breakpoints(MAP_AXIS)
    for row in range(16):
        vehicle_state.set_ignition_row(base_row(row), row)
    screen.on_activated()
    environment = Env(screen, connection, clock, tmp_path)
    environment.gyro = gyro
    yield environment
    screen.on_deactivated()
    write_module.get_ecu_connection = write_module_original


def box(env):
    env.screen._refresh()
    label = env.screen.inclination_label
    return label.text(), label.styleSheet()


@pytest.mark.parametrize("pitch, text, color", [
    (1.37, "Inclinação: +1.4° ↓", "#2ECC71"),       # Scenario: Nose down
    (-2.04, "Inclinação: -2.0° ↑", "#2ECC71"),      # Scenario: Nose up
    (0.02, "Inclinação: 0.0°", "#2ECC71"),          # Scenario: Flat
    (-0.04, "Inclinação: 0.0°", "#2ECC71"),
    (4.5, "Inclinação: +4.5° ↓", "#E74C3C"),        # Scenario: Above the limit
    (-4.5, "Inclinação: -4.5° ↑", "#E74C3C"),
    (3.0, "Inclinação: +3.0° ↓", "#2ECC71"),
])
def test_inclination_box_when_usable(tilt_env, pitch, text, color):
    """Spec: Inclination box (nose down, nose up, flat, above the limit)."""
    tilt_env.gyro.use(pitch)

    shown, style = box(tilt_env)

    assert shown == text
    assert color in style


@pytest.mark.parametrize("status, text, color", [
    (GyroStatus.NOT_ZEROED, "Inclinação: sem zero (G)", "#FF8800"),     # Scenario: Not zeroed
    (GyroStatus.NO_SIGNAL, "Inclinação: sem sinal", "#FF8800"),         # Scenario: No signal
    (GyroStatus.DISCONNECTED, "Inclinação: desconectada", "#FF8800"),   # Scenario: Disconnected
    (GyroStatus.DISABLED, "Inclinação: desligada", "#777777"),          # Scenario: Disabled
])
def test_inclination_box_when_not_usable(tilt_env, status, text, color):
    tilt_env.gyro.status = status

    shown, style = box(tilt_env)

    assert shown == text
    assert color in style


def test_inclination_box_never_reads_calibrating(tilt_env):
    """Scenario: Calibrating. An old firmware's retired `#C;CALIBRANDO;` reply changes nothing in the box."""
    from app.gyro.state import GyroState
    state = GyroState()
    state.set_enabled(True)
    state.opened()
    state.feed("#D;100;1.0;0.0;0.0;0.0;1.0;27.0;")
    before = state.snapshot().status

    state.feed("#C;CALIBRANDO;")
    tilt_env.gyro.status = state.snapshot().status
    shown, _ = box(tilt_env)

    assert state.snapshot().status is before is GyroStatus.NOT_ZEROED
    assert shown == "Inclinação: sem zero (G)"
    assert "calibrando" not in shown


def test_inclination_box_follows_the_configured_limit(tilt_env):
    tilt_env.gyro.use(4.5)
    config.ignition_tuning.max_tilt_deg = 5
    tilt_env.screen.on_setting_changed("ignition_tuning", "max_tilt_deg")

    assert "#2ECC71" in box(tilt_env)[1]


def status(env):
    env.screen._refresh()
    return env.screen.status_label.text()


def test_status_waits_for_the_sensor(tilt_env):
    """Scenario: Waiting for the sensor."""
    tilt_env.gyro.status = GyroStatus.NOT_ZEROED

    assert status(tilt_env) == "AGUARDANDO SENSOR"


def test_the_sensor_has_priority_over_the_band(tilt_env):
    """Scenario: Sensor has priority over the band."""
    tilt_env.gyro.status = GyroStatus.DISCONNECTED
    tilt_env.publish(rpm=3400)

    assert status(tilt_env) == "AGUARDANDO SENSOR"


def test_status_is_tilted_above_the_limit(tilt_env):
    """Scenario: Tilted."""
    tilt_env.gyro.use(4.5)

    assert status(tilt_env) == "INCLINADO"


def test_status_settles_and_then_analyses_after_the_car_is_level(tilt_env):
    """Scenario: Settling after the inclination is level."""
    tilt_env.gyro.use(4.5)
    tilt_env.feed(1.0)
    tilt_env.gyro.use(1.0)
    tilt_env.publish()

    assert status(tilt_env) == "ESTABILIZANDO"
    tilt_env.feed(5.5)
    assert status(tilt_env) == "ANALISANDO"


def test_status_never_shows_the_sensor_states_without_a_configured_sensor(env):
    """Scenario: No sensor configured."""
    env.settle()
    env.feed(1.0)
    env.screen._refresh()

    assert env.screen.status_label.text() == "ANALISANDO"
    assert env.screen.inclination_label.text() == "Inclinação: desligada"


def test_a_tilted_car_is_not_analysed(tilt_env):
    tilt_env.gyro.use(5.0)
    tilt_env.feed(8.0)

    assert tilt_env.screen._analysis.gears_with_data() == []


def test_a_level_car_is_analysed(tilt_env):
    tilt_env.feed(8.0)
    tilt_env.feed(2.0)

    assert tilt_env.screen._analysis.gears_with_data() == [5]


def test_g_zeroes_the_inclinometer_and_changes_nothing_else(tilt_env):
    """Scenario: Zero the inclination."""
    tilt_env.settle()
    tilt_env.feed(1.0)
    offset, paused = tilt_env.state.offset, tilt_env.screen._analysis.paused
    revision = tilt_env.screen._analysis.revision

    tilt_env.press(Qt.Key.Key_G)

    assert tilt_env.gyro.zero_calls == 1
    assert (tilt_env.state.offset, tilt_env.screen._analysis.paused) == (offset, paused)
    assert tilt_env.screen._analysis.revision == revision
    assert tilt_env.connection.sent == []


def test_g_is_ignored_when_held(tilt_env):
    tilt_env.press(Qt.Key.Key_G, auto_repeat=True)

    assert tilt_env.gyro.zero_calls == 0


def test_g_without_a_sensor_sends_nothing_and_changes_nothing(env):
    """Scenario: Zero without a sensor. The default inclinometer is disabled, so it drops the command."""
    env.settle()
    offset = env.state.offset

    env.press(Qt.Key.Key_G)

    assert env.state.offset == offset
    assert env.connection.sent == []
    assert env.screen._gyro.zero() is False


# -- settings changed on the Settings screen

def test_a_new_rpm_band_writes_the_previous_run_with_its_own_band_and_starts_a_new_file(tilt_env):
    """Spec: a change of the RPM band ends the results of the run, written with the old band."""
    tilt_env.feed(8.0)
    tilt_env.feed(2.0)
    assert tilt_env.screen._analysis.gears_with_data() == [5]

    config.ignition_tuning.rpm_max = 3200
    tilt_env.screen.on_setting_changed("ignition_tuning", "rpm_max")

    first = result_files(tilt_env)
    assert len(first) == 1
    assert {row[3] for row in result_rows(tilt_env, first[0])} == {"3100"}
    assert tilt_env.screen._analysis.gears_with_data() == []
    assert tilt_env.screen._analysis.rpm_max == 3200

    tilt_env.feed(1.0, rpm=3150)
    files = result_files(tilt_env)
    assert len(files) == 2
    assert {row[3] for row in result_rows(tilt_env, files[1])} == {"3200"}


def test_another_ignition_setting_keeps_the_scenarios_and_the_run(tilt_env):
    tilt_env.feed(8.0)
    tilt_env.feed(2.0)
    config.ignition_tuning.settle_seconds = 8

    tilt_env.screen.on_setting_changed("ignition_tuning", "settle_seconds")

    assert tilt_env.screen._analysis.gears_with_data() == [5]
    assert tilt_env.screen._analysis.settle_seconds == 8


def test_settings_of_other_sections_are_ignored(tilt_env):
    tilt_env.feed(8.0)
    tilt_env.feed(2.0)
    config.ignition_tuning.rpm_max = 3200  # changed behind the screen's back

    tilt_env.screen.on_setting_changed("gyro", "port")

    assert tilt_env.screen._analysis.rpm_max == 3100
    assert tilt_env.screen._analysis.gears_with_data() == [5]


def test_both_top_bar_lines_share_columns_and_the_box_sits_right_of_the_temperatures(tilt_env):
    """Spec: Top bar (second line order and column widths) and Inclination box (position)."""
    screen = tilt_env.screen
    screen.resize(1920, 1080)
    screen.show()
    screen._refresh()
    cards = screen._top_bar_cards
    clt, iat = (screen._second_line_cards[signal] for signal in screen._second_line_cards)
    rpm, pedal = cards[Signal.RPM], cards[Signal.PEDAL]

    assert abs(clt.width() - rpm.width()) <= 2 and abs(iat.width() - pedal.width()) <= 2
    def left(widget):
        return widget.mapTo(screen, widget.rect().topLeft()).x()

    def right(widget):
        return widget.mapTo(screen, widget.rect().topRight()).x()

    def top(widget):
        return widget.mapTo(screen, widget.rect().topLeft()).y()

    box = screen.inclination_label
    assert left(clt) < left(iat) < left(box) < left(screen.gear_label) < left(screen.band_label)
    assert right(iat) <= left(box) and right(box) <= left(screen.gear_label)
    assert top(box) > top(rpm)  # on the second line
    screen.hide()
