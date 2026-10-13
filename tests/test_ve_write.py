"""Spec: openspec/specs/ve-write."""
import time
from unittest.mock import Mock

import pytest

import app.ui.ve_calibration.ve_write_controller as controller_module
from app.masterinjection.protocol import EcuCommand
from app.ui.ve_calibration.ve_map_state import VeMapState
from app.ui.ve_calibration.ve_write_controller import VeWriteController
from tests.helpers import MAP_AXIS, RPM_AXIS


class RecordingConnection:
    def __init__(self):
        self.sent = []

    def send_command(self, cmd, args=None):
        self.sent.append((cmd, list(args or [])))


@pytest.fixture
def env(qapp, monkeypatch):
    model = VeMapState()
    model.load_breakpoints_rpm(RPM_AXIS)
    model.load_breakpoints_map(MAP_AXIS)
    for row in range(16):
        model.load_row(row, [800 + row * 16 + col for col in range(16)])
    connection = RecordingConnection()
    monkeypatch.setattr(controller_module, "ve_map_state", model)
    monkeypatch.setattr(controller_module, "get_ecu_connection", lambda: connection)
    controller = VeWriteController("does-not-exist.wav")
    controller._player = Mock()
    return model, connection, controller


def expire(controller):
    """Simulate the 1 s delay elapsing without waiting for it."""
    controller._timer.timeout.emit()


# ----------------------------------------------------------------- write delay

def test_adjustment_starts_a_one_second_single_shot_delay(env):
    """Requirement: Write delay."""
    _, _, controller = env

    controller.on_adjustment_made()

    assert controller._timer.isActive()
    assert controller._timer.isSingleShot()
    assert controller._timer.interval() == 1000


def test_each_adjustment_restarts_the_delay(env):
    """Scenario: Burst of edits."""
    _, _, controller = env
    controller.on_adjustment_made()
    time.sleep(0.15)
    elapsed_remaining = controller._timer.remainingTime()

    controller.on_adjustment_made()

    assert controller._timer.remainingTime() > elapsed_remaining


def test_nothing_is_sent_before_the_delay_elapses(env):
    model, connection, controller = env
    model.set_cell(3, 2, model.get_cell(3, 2) + 5)

    controller.on_adjustment_made()

    assert connection.sent == []


# ------------------------------------------------------------- row-by-row write

def test_pending_rows_are_written_in_ascending_order_with_all_sixteen_values(env):
    """Scenario: Two rows edited."""
    model, connection, controller = env
    model.set_cell(7, 1, model.get_cell(7, 1) + 5)
    model.set_cell(3, 2, model.get_cell(3, 2) + 5)

    expire(controller)

    assert [cmd for cmd, _ in connection.sent] == [EcuCommand.VE_ROW_4, EcuCommand.VE_ROW_8]
    assert connection.sent[0][1] == model.get_row_raw_values(3)
    assert len(connection.sent[0][1]) == 16 and len(connection.sent[1][1]) == 16
    assert connection.sent[0][1][2] == 800 + 3 * 16 + 2 + 5  # the edited value is included


def test_row_command_wire_text_matches_the_row_number(env):
    model, connection, controller = env
    model.set_cell(4, 0, model.get_cell(4, 0) + 1)

    expire(controller)

    cmd, args = connection.sent[0]
    assert cmd.cmd == "#F05"
    assert f"{cmd.cmd};" + ";".join(map(str, args)) == "#F05;" + ";".join(map(str, model.get_row_raw_values(4)))


def test_written_rows_are_not_written_again_unless_edited_again(env):
    """Scenario: Not rewritten."""
    model, connection, controller = env
    model.set_cell(3, 2, model.get_cell(3, 2) + 5)
    expire(controller)
    connection.sent.clear()

    expire(controller)
    assert connection.sent == []

    model.set_cell(3, 2, model.get_cell(3, 2) + 5)
    expire(controller)
    assert [cmd for cmd, _ in connection.sent] == [EcuCommand.VE_ROW_4]


def test_write_on_memory_command_is_never_sent(env):
    """Requirement: Row-by-row write (no #D04)."""
    model, connection, controller = env
    model.reset()

    expire(controller)

    assert EcuCommand.WRITE_ON_MEMORY not in [cmd for cmd, _ in connection.sent]


# ---------------------------------------------------------------- nothing to do

def test_nothing_pending_sends_nothing_and_plays_no_sound(env):
    """Requirement: Nothing to write."""
    _, connection, controller = env

    expire(controller)

    assert connection.sent == []
    controller._player.play.assert_not_called()


def test_edit_undone_within_the_delay_sends_nothing(env):
    """Scenario: Edit undone."""
    model, connection, controller = env
    original = model.get_cell(5, 5)
    model.set_cell(5, 5, original + 5)
    model.set_cell(5, 5, original)

    expire(controller)

    assert connection.sent == []


# ----------------------------------------------------------------------- sound

def test_sound_plays_once_per_batch(env):
    """Scenario: Batch sent."""
    model, _, controller = env
    model.set_cell(1, 1, model.get_cell(1, 1) + 5)
    model.set_cell(9, 9, model.get_cell(9, 9) + 5)

    expire(controller)

    controller._player.stop.assert_called_once()
    controller._player.play.assert_called_once()


# ----------------------------------------------------------------------- reset

def test_write_after_reset_sends_all_sixteen_rows(env):
    """Scenario: Reset."""
    model, connection, controller = env
    model.set_cell(2, 2, model.get_cell(2, 2) + 50)
    model.reset()

    expire(controller)

    assert [cmd for cmd, _ in connection.sent] == [EcuCommand[f"VE_ROW_{n}"] for n in range(1, 17)]
    assert connection.sent[2][1] == [800 + 2 * 16 + col for col in range(16)]  # original values, not the edit
