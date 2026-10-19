"""Spec: openspec/specs/phase-write and the #X02 part of openspec/specs/ecu-protocol."""
import pytest

from app.masterinjection.protocol import (
    EcuCommand, EcuResponse, Phase, X02_PHASE_INDEX, parse_x02, x02_phase, x02_with_phase,
)
from app.state.state import vehicle_state
from app.ui.options.phase_write_controller import (
    ANSWER_TIMEOUT_MS, PhaseWriteController, STATUS_APPLIED, STATUS_INVALID, STATUS_NO_ANSWER,
    STATUS_PENDING, STATUS_SENDING, WRITE_DELAY_MS,
)

NEGATIVE_LINE = "#X02;600;400;6;0;117;8000;6100;6300;5;2000;1750;0;1960;2;100;2"
POSITIVE_LINE = "#X02;600;400;6;0;117;8000;6100;6300;5;2000;1750;1;1960;2;100;2"


# --------------------------------------------------------------- protocol: #X02

def test_parameter_block_command_and_response_use_the_x02_prefix():
    """Requirement: Command catalog / Response catalog (#X02)."""
    assert EcuCommand.PARAMETERS_X02.cmd == "#X02"
    assert EcuResponse.PARAMETERS_X02.value == "#X02"


def test_phase_is_at_position_11_of_the_block():
    """Requirement: Engine phase in the parameter block."""
    assert X02_PHASE_INDEX == 11


def test_block_with_phase_zero_is_negativa():
    """Scenario: Phase values."""
    block = parse_x02(NEGATIVE_LINE)

    assert len(block) == 16
    assert x02_phase(block) is Phase.NEGATIVE
    assert Phase.NEGATIVE.label == "Negativa"


def test_block_with_phase_one_is_positiva():
    """Scenario: Positive phase."""
    assert x02_phase(parse_x02(POSITIVE_LINE)) is Phase.POSITIVE
    assert Phase.POSITIVE.label == "Positiva"


def test_unexpected_phase_value_or_missing_block_has_no_phase():
    """Requirement: Phase display (unknown / unexpected)."""
    assert x02_phase(None) is None
    assert x02_phase([0] * 11 + [2] + [0] * 4) is None


@pytest.mark.parametrize("line", [
    "#X02;" + ";".join(["1"] * 15),
    "#X02;" + ";".join(["1"] * 17),
    "#X02;" + ";".join(["1"] * 15) + ";x",
    "#X02",
    "#F01;" + ";".join(["1"] * 16),
])
def test_parse_rejects_anything_but_sixteen_integers_after_the_prefix(line):
    """Requirement: Invalid or missing answers (an answer is valid only with 16 integers)."""
    assert parse_x02(line) is None


def test_only_the_phase_value_changes():
    """Requirement: Only the phase changes."""
    block = parse_x02(NEGATIVE_LINE)

    changed = x02_with_phase(block, Phase.POSITIVE)

    assert ["#X02"] + [str(v) for v in changed] == POSITIVE_LINE.split(";")
    assert [v for i, v in enumerate(changed) if i != X02_PHASE_INDEX] == [v for i, v in enumerate(block) if i != X02_PHASE_INDEX]
    assert block == parse_x02(NEGATIVE_LINE)  # the input is not mutated


def test_opposite_phase():
    assert Phase.NEGATIVE.opposite is Phase.POSITIVE
    assert Phase.POSITIVE.opposite is Phase.NEGATIVE


# ------------------------------------------------------------------ controller

NEGATIVE_BLOCK = parse_x02(NEGATIVE_LINE)
POSITIVE_BLOCK = parse_x02(POSITIVE_LINE)


class Env:
    def __init__(self, controller):
        self.controller = controller
        self.sent = []

    def lines(self):
        """The commands queued so far, as wire text."""
        return [cmd.cmd + ("".join(";" + str(v) for v in args) if args else "") for cmd, args in self.sent]

    def delay(self):
        self.controller._delay_timer.timeout.emit()

    def timeout(self):
        self.controller._answer_timer.timeout.emit()

    def answer(self, line):
        self.controller.on_line_received(line)


@pytest.fixture
def env(qapp):
    sent = []
    beeps = []
    controller = PhaseWriteController(
        send_command=lambda cmd, args=None: sent.append((cmd, list(args) if args else None)),
        get_block=vehicle_state.get_x02,
        set_block=vehicle_state.set_x02,
        on_written=lambda: beeps.append(len(sent)),
    )
    e = Env(controller)
    e.sent = sent
    e.beeps = beeps
    vehicle_state.set_x02(NEGATIVE_BLOCK)
    return e


def test_toggle_starts_a_one_second_single_shot_delay(env):
    """Requirement: Write delay."""
    env.controller.toggle()

    timer = env.controller._delay_timer
    assert timer.isActive() and timer.isSingleShot() and timer.interval() == WRITE_DELAY_MS == 1000
    assert env.controller.status == STATUS_PENDING
    assert env.sent == []


def test_each_toggle_restarts_the_delay_and_the_last_request_wins(env):
    """Scenario: Burst of toggles."""
    starts = []
    timer = env.controller._delay_timer
    real_start = timer.start
    timer.start = lambda *args: (starts.append(args), real_start(*args))[1]

    env.controller.toggle()   # Positiva
    env.controller.toggle()   # Negativa
    env.controller.toggle()   # Positiva

    assert len(starts) == 3
    env.delay()
    assert env.lines() == ["#X02"]
    env.answer(NEGATIVE_LINE)
    assert env.lines()[1] == POSITIVE_LINE


def test_toggle_shows_the_requested_phase_until_the_sequence_ends(env):
    """Requirement: Phase display (change in progress)."""
    assert env.controller.displayed_phase() is Phase.NEGATIVE

    env.controller.toggle()

    assert env.controller.displayed_phase() is Phase.POSITIVE
    assert env.controller.in_progress


def test_toggle_with_unknown_phase_does_nothing(qapp):
    """Scenario: Unknown phase (toggle)."""
    sent = []
    controller = PhaseWriteController(lambda cmd, args=None: sent.append(cmd), lambda: None, lambda v: None)

    controller.toggle()

    assert not controller._delay_timer.isActive()
    assert not controller.in_progress and sent == []


def test_elapsed_delay_requests_the_block_first_and_writes_nothing_yet(env):
    """Scenario: Request first."""
    env.controller.toggle()
    env.delay()

    assert env.lines() == ["#X02"]
    assert env.controller.status == STATUS_SENDING
    assert env.controller._answer_timer.isActive()


def test_negative_to_positive_writes_the_block_with_only_the_phase_changed(env):
    """Scenario: Negative to positive."""
    env.controller.toggle()
    env.delay()
    env.answer(NEGATIVE_LINE)

    assert env.lines() == ["#X02", POSITIVE_LINE, "#X02"]


def test_positive_to_negative_writes_the_block_with_only_the_phase_changed(env):
    """Scenario: Positive to negative."""
    vehicle_state.set_x02(POSITIVE_BLOCK)
    env.controller.toggle()
    env.delay()
    env.answer(POSITIVE_LINE)

    assert env.lines() == ["#X02", NEGATIVE_LINE, "#X02"]


def test_the_block_written_comes_from_the_fresh_answer(env):
    """Scenario: Fresh block used."""
    fresh = NEGATIVE_LINE.replace("#X02;600", "#X02;777")
    env.controller.toggle()
    env.delay()
    env.answer(fresh)

    assert env.lines()[1] == POSITIVE_LINE.replace("#X02;600", "#X02;777")


def test_toggled_back_only_the_request_is_queued(env):
    """Scenario: Toggled back."""
    env.controller.toggle()
    env.controller.toggle()
    env.delay()
    env.answer(NEGATIVE_LINE)

    assert env.lines() == ["#X02"]
    assert env.controller.status == STATUS_APPLIED
    assert not env.controller.in_progress


def test_a_complete_change_never_sends_write_on_memory(env):
    """Scenario: Complete change."""
    env.controller.toggle()
    env.delay()
    env.answer(NEGATIVE_LINE)
    env.answer(POSITIVE_LINE)

    assert env.lines() == ["#X02", POSITIVE_LINE, "#X02"]
    assert EcuCommand.WRITE_ON_MEMORY not in [cmd for cmd, _ in env.sent]


def test_confirmation_with_the_requested_phase_means_applied(env):
    """Scenario: Applied."""
    env.controller.toggle()
    env.delay()
    env.answer(NEGATIVE_LINE)
    env.answer(POSITIVE_LINE)

    assert env.controller.status == STATUS_APPLIED
    assert env.controller.displayed_phase() is Phase.POSITIVE
    assert not env.controller.in_progress
    assert not env.controller._answer_timer.isActive()


def test_confirmation_with_the_old_phase_means_not_applied(env):
    """Scenario: Not applied."""
    env.controller.toggle()
    env.delay()
    env.answer(NEGATIVE_LINE)
    env.answer(NEGATIVE_LINE)

    assert env.controller.status == "A ECU manteve a fase Negativa"
    assert env.controller.displayed_phase() is Phase.NEGATIVE
    assert not env.controller.in_progress


def test_unrelated_lines_are_ignored_while_waiting(env):
    """Scenario: Unrelated line."""
    env.controller.toggle()
    env.delay()

    env.answer("#D03;1;2")
    env.answer("#I21;1;2")

    assert env.lines() == ["#X02"]
    assert env.controller.in_progress


def test_a_line_without_a_change_is_published_and_nothing_is_written(env):
    """Scenario: Refresh without a change."""
    env.answer(POSITIVE_LINE)

    assert vehicle_state.get_x02() == POSITIVE_BLOCK
    assert env.controller.displayed_phase() is Phase.POSITIVE
    assert env.sent == []


@pytest.mark.parametrize("line", ["#X02;" + ";".join(["1"] * 15), "#X02;" + ";".join(["1"] * 15) + ";abc"])
def test_invalid_read_answer_writes_nothing(env, line):
    """Scenarios: Wrong value count / Non-numeric value."""
    env.controller.toggle()
    env.delay()
    env.answer(line)

    assert env.lines() == ["#X02"]
    assert env.controller.status == STATUS_INVALID
    assert env.controller.displayed_phase() is Phase.NEGATIVE
    assert vehicle_state.get_x02() == NEGATIVE_BLOCK


def test_invalid_confirmation_keeps_the_previous_block(env):
    """Scenario: Invalid confirmation."""
    env.controller.toggle()
    env.delay()
    env.answer(NEGATIVE_LINE)
    env.answer("#X02;" + ";".join(["1"] * 15))

    assert env.controller.status == STATUS_INVALID
    assert vehicle_state.get_x02() == NEGATIVE_BLOCK
    assert not env.controller.in_progress


def test_read_timeout_writes_nothing(env):
    """Scenario: Read timeout."""
    env.controller.toggle()
    env.delay()
    assert env.controller._answer_timer.interval() == ANSWER_TIMEOUT_MS == 2000

    env.timeout()

    assert env.lines() == ["#X02"]
    assert env.controller.status == STATUS_NO_ANSWER
    assert env.controller.displayed_phase() is Phase.NEGATIVE


def test_confirmation_timeout_reverts_to_the_last_published_phase(env):
    """Scenario: Confirmation timeout."""
    env.controller.toggle()
    env.delay()
    env.answer(NEGATIVE_LINE)

    env.timeout()

    assert env.controller.status == STATUS_NO_ANSWER
    assert env.controller.displayed_phase() is Phase.NEGATIVE
    assert len(env.sent) == 3


def test_late_timeout_after_an_answer_does_nothing(env):
    env.controller.toggle()
    env.delay()
    env.answer(NEGATIVE_LINE)
    env.answer(POSITIVE_LINE)

    env.timeout()

    assert env.controller.status == STATUS_APPLIED


def test_toggle_while_the_confirmation_is_pending_starts_a_new_sequence(env):
    """Scenario: Toggle after the write."""
    env.controller.toggle()
    env.delay()
    env.answer(NEGATIVE_LINE)

    env.controller.toggle()   # displayed Positiva -> requests Negativa

    assert not env.controller._answer_timer.isActive()
    assert env.controller._delay_timer.isActive()
    assert env.controller.displayed_phase() is Phase.NEGATIVE
    env.delay()
    env.answer(POSITIVE_LINE)
    assert env.lines()[-2:] == [NEGATIVE_LINE, "#X02"]


def test_refresh_requests_the_block_without_arguments_unless_a_change_is_in_progress(env):
    """Requirement: Refresh on activation."""
    env.controller.request_refresh()
    assert env.lines() == ["#X02"]

    env.controller.toggle()
    env.controller.request_refresh()
    assert env.lines() == ["#X02"]


def test_changed_signal_fires_on_toggle_and_on_result(env):
    fired = []
    env.controller.changed.connect(lambda: fired.append(1))

    env.controller.toggle()
    env.delay()
    env.answer(NEGATIVE_LINE)
    env.answer(POSITIVE_LINE)

    assert len(fired) >= 4


def test_success_status_can_be_cleared_but_failures_stay(env):
    env.controller.toggle()
    env.delay()
    env.timeout()
    env.controller.clear_success_status()
    assert env.controller.status == STATUS_NO_ANSWER

    env.controller.toggle()
    env.controller.toggle()
    env.delay()
    env.answer(NEGATIVE_LINE)
    env.controller.clear_success_status()
    assert env.controller.status == ""


# ----------------------------------------------------------------- write sound

def test_sound_plays_once_when_the_block_is_written(env):
    """Scenario: Block written (the beep comes right after the write is queued, before the confirmation)."""
    env.controller.toggle()
    env.delay()
    env.answer(NEGATIVE_LINE)

    assert env.beeps == [2]
    env.answer(POSITIVE_LINE)
    assert env.beeps == [2]


def test_requests_are_silent(env):
    """Scenario: Requests are silent."""
    env.controller.toggle()
    env.delay()
    env.controller.request_refresh()

    assert env.beeps == []


def test_no_sound_when_the_phase_is_already_applied(env):
    """Scenario: Already applied."""
    env.controller.toggle()
    env.controller.toggle()
    env.delay()
    env.answer(NEGATIVE_LINE)

    assert env.beeps == []


def test_no_sound_when_the_read_fails(env):
    """Scenario: Failed read."""
    env.controller.toggle()
    env.delay()
    env.timeout()
    env.controller.toggle()
    env.delay()
    env.answer("#X02;1;2")

    assert env.beeps == []
