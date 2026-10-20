"""Spec: openspec/specs/settings-screen, requirement "Calibration wizard" (the flow, without Qt).

The wizard runs against a real `GyroState` fed with the lines the firmware prints, and a fake clock, so the order of
the device's answers and the timeouts are exercised exactly.
"""
import pytest

from app.gyro.protocol import CALIBRATION_POSITIONS
from app.gyro.state import GyroState
from app.ui.settings.calibration import CalibrationWizard, CloseReason, Phase

REPORT = "#K;OFFSET;0.0100;-0.0200;-0.3450;SCALE;1.0000;1.0000;1.0350;"
SAVED = "#M;CALIBRACAO_SALVA;"
INVALID = "#M;CALIBRACAO_INVALIDA_REPITA_AS_POSICOES;"


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Gyro:
    """What the wizard needs of the inclinometer: the state, and the capture commands it was asked to send."""

    def __init__(self, clock):
        self.state = GyroState(clock)
        self.state.set_enabled(True)
        self.state.opened()
        self.open = True
        self.sent = []

    def snapshot(self):
        return self.state.snapshot()

    def capture(self, position):
        self.sent.append(position)
        return self.open

    def hear(self, *lines):
        for line in lines:
            self.state.feed(line)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def gyro(clock):
    g = Gyro(clock)
    g.hear("#D;1000;0;0;0;0;1;30;")  # the stream is alive
    return g


@pytest.fixture
def wizard(gyro, clock):
    return CalibrationWizard(gyro, clock)


def capture_step(wizard, gyro, clock=None):
    """Enter on the current step, and the device's acknowledgement."""
    command = CALIBRATION_POSITIONS[wizard.step_number - 1]
    wizard.confirm()
    gyro.hear(f"{command};OK;")
    wizard.update()


def to_the_last_step(wizard, gyro):
    for _ in range(5):
        capture_step(wizard, gyro)


# ── Steps ────────────────────────────────────────────────────────────────────────────────────────────────

def test_first_step(wizard):
    """Scenario: First step."""
    assert wizard.progress_text == "Passo 1 de 6"
    assert wizard.instruction_text == "Eixo Z para cima. Mantenha a placa parada"
    assert wizard.phase is Phase.WAITING and wizard.status_text == "" and not wizard.closed


def test_enter_sends_the_capture_command_of_the_step(wizard, gyro):
    """Scenario: Capture sent."""
    wizard.confirm()

    assert gyro.sent == ["#KZU"] and wizard.status_text == "Capturando…" and wizard.phase is Phase.CAPTURING


def test_enter_is_ignored_while_capturing(wizard, gyro):
    """Scenario: Keys ignored while capturing."""
    wizard.confirm()
    wizard.confirm()
    wizard.confirm()

    assert gyro.sent == ["#KZU"] and wizard.step_number == 1


def test_the_acknowledgement_advances_to_the_next_step(wizard, gyro):
    """Scenario: Acknowledgement advances."""
    wizard.confirm()
    gyro.hear("#KZU;OK;")
    wizard.update()

    assert wizard.progress_text == "Passo 2 de 6"
    assert wizard.instruction_text == "Eixo Z para baixo. Mantenha a placa parada"
    assert wizard.phase is Phase.WAITING and wizard.status_text == ""


def test_the_acknowledgement_of_another_position_does_not_advance(wizard, gyro):
    wizard.confirm()
    gyro.hear("#KXU;OK;")
    wizard.update()

    assert wizard.step_number == 1 and wizard.phase is Phase.CAPTURING


def test_six_steps_in_order(wizard, gyro):
    """Scenario: Six steps in order."""
    for _ in range(6):
        capture_step(wizard, gyro)

    assert gyro.sent == ["#KZU", "#KZD", "#KXU", "#KXD", "#KYU", "#KYD"]


def test_the_instructions_name_each_position(wizard, gyro):
    names = []
    for _ in range(6):
        names.append(wizard.instruction_text.split(".")[0])
        capture_step(wizard, gyro)

    assert names == ["Eixo Z para cima", "Eixo Z para baixo", "Eixo X para cima", "Eixo X para baixo",
                     "Eixo Y para cima", "Eixo Y para baixo"]


def test_nothing_moves_by_itself_without_an_update(wizard, gyro):
    wizard.confirm()
    gyro.hear("#KZU;OK;")

    assert wizard.step_number == 1  # the wizard follows the device only when it is updated


def test_without_an_acknowledgement_the_step_is_repeated(wizard, gyro, clock):
    """Scenario: No acknowledgement."""
    wizard.confirm()
    clock.now += 2.9
    wizard.update()
    assert wizard.phase is Phase.CAPTURING

    clock.now += 0.2
    wizard.update()

    assert wizard.status_text == "Sem resposta do inclinômetro" and wizard.step_number == 1
    assert wizard.phase is Phase.WAITING
    wizard.confirm()
    assert gyro.sent == ["#KZU", "#KZU"]


def test_the_late_acknowledgement_of_a_timed_out_step_is_not_lost_on_retry(wizard, gyro, clock):
    wizard.confirm()
    clock.now += 4
    wizard.update()
    wizard.confirm()
    gyro.hear("#KZU;OK;")
    wizard.update()

    assert wizard.step_number == 2


# ── Outcome ──────────────────────────────────────────────────────────────────────────────────────────────

def test_after_the_sixth_acknowledgement_it_waits_for_the_result(wizard, gyro):
    """Scenario: Waiting for the result."""
    to_the_last_step(wizard, gyro)
    capture_step(wizard, gyro)

    assert wizard.phase is Phase.CALCULATING and wizard.status_text == "Calculando…"
    assert wizard.step_number == 6


def test_a_saved_calibration_ends_the_wizard_after_enter(wizard, gyro):
    """Scenario: Calibration saved."""
    to_the_last_step(wizard, gyro)
    wizard.confirm()
    gyro.hear("#KYD;OK;", SAVED, REPORT)
    wizard.update()

    assert wizard.phase is Phase.SAVED and wizard.status_text == "Calibração salva"
    assert not wizard.closed
    wizard.confirm()
    assert wizard.closed and wizard.close_reason is CloseReason.DONE


def test_a_saved_calibration_is_also_closed_by_escape_without_a_cancel(wizard, gyro):
    to_the_last_step(wizard, gyro)
    wizard.confirm()
    gyro.hear("#KYD;OK;", SAVED)
    wizard.update()

    wizard.cancel()

    assert wizard.close_reason is CloseReason.DONE


def test_the_outcome_is_seen_even_when_the_update_misses_the_last_acknowledgement(wizard, gyro):
    """The device prints the sixth OK and the outcome back to back, and the outcome clears the acknowledgements."""
    to_the_last_step(wizard, gyro)
    wizard.confirm()
    gyro.hear("#KYD;OK;", SAVED)  # both before the next refresh
    wizard.update()

    assert wizard.phase is Phase.SAVED


def test_an_invalid_calibration_restarts_at_the_first_step(wizard, gyro):
    """Scenario: Calibration invalid."""
    to_the_last_step(wizard, gyro)
    wizard.confirm()
    gyro.hear("#KYD;OK;", INVALID)
    wizard.update()
    assert wizard.phase is Phase.INVALID and wizard.status_text == "Calibração inválida, repita as posições"

    wizard.confirm()

    assert wizard.step_number == 1 and wizard.phase is Phase.WAITING and not wizard.closed
    wizard.confirm()
    assert gyro.sent[-1] == "#KZU"


def test_an_invalid_calibration_can_be_closed(wizard, gyro):
    """Scenario: Invalid, then close."""
    to_the_last_step(wizard, gyro)
    wizard.confirm()
    gyro.hear("#KYD;OK;", INVALID)
    wizard.update()

    wizard.cancel()

    assert wizard.closed and wizard.close_reason is CloseReason.DONE


def test_without_a_result_the_run_counts_as_invalid(wizard, gyro, clock):
    """Scenario: No result."""
    to_the_last_step(wizard, gyro)
    capture_step(wizard, gyro)
    clock.now += 3.1
    wizard.update()

    assert wizard.phase is Phase.INVALID and wizard.status_text == "Sem resultado da calibração"
    wizard.confirm()
    assert wizard.step_number == 1 and wizard.phase is Phase.WAITING


def test_an_old_outcome_does_not_end_a_new_run(wizard, gyro):
    gyro.hear(SAVED)  # the outcome of an earlier run is still in the state
    wizard.confirm()
    wizard.update()

    assert wizard.phase is Phase.CAPTURING and wizard.step_number == 1
    gyro.hear("#KZU;OK;")  # a capture of this run clears it
    wizard.update()
    assert wizard.step_number == 2


# ── Cancel and disconnect ────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("steps", [0, 2])
def test_escape_cancels(wizard, gyro, steps):
    """Scenario: Cancel."""
    for _ in range(steps):
        capture_step(wizard, gyro)
    sent = list(gyro.sent)

    wizard.cancel()

    assert wizard.closed and wizard.close_reason is CloseReason.CANCELLED
    assert gyro.sent == sent  # the wizard sends nothing to undo the captures


def test_escape_while_capturing_cancels(wizard, gyro):
    wizard.confirm()

    wizard.cancel()

    assert wizard.close_reason is CloseReason.CANCELLED


def test_a_new_wizard_starts_at_the_first_step_after_a_cancel(wizard, gyro, clock):
    """Scenario: Start again after cancelling."""
    capture_step(wizard, gyro)
    capture_step(wizard, gyro)
    wizard.cancel()

    again = CalibrationWizard(gyro, clock)

    assert again.progress_text == "Passo 1 de 6"


def test_a_closed_wizard_ignores_everything(wizard, gyro):
    wizard.cancel()
    wizard.confirm()
    wizard.update()

    assert gyro.sent == [] and wizard.close_reason is CloseReason.CANCELLED


@pytest.mark.parametrize("phase_steps", [0, 1])
def test_a_lost_port_closes_the_wizard(wizard, gyro, phase_steps):
    """Scenario: Port lost."""
    for _ in range(phase_steps):
        capture_step(wizard, gyro)
    gyro.state.closed()

    wizard.update()

    assert wizard.closed and wizard.close_reason is CloseReason.DISCONNECTED


def test_a_port_that_is_not_configured_closes_the_wizard(wizard, gyro):
    gyro.state.set_enabled(False)

    wizard.update()

    assert wizard.close_reason is CloseReason.DISCONNECTED


def test_a_capture_that_could_not_be_sent_closes_the_wizard(wizard, gyro):
    gyro.open = False

    wizard.confirm()

    assert wizard.close_reason is CloseReason.DISCONNECTED
