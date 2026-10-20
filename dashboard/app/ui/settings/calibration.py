import enum
import time
from collections.abc import Callable
from typing import Optional

from app.gyro.protocol import CALIBRATION_POSITIONS
from app.gyro.state import GyroSnapshot, GyroStatus, OUTCOME_INVALID, OUTCOME_SAVED

# How long the wizard waits for the device's answer to a capture (the device needs about 0.5 s) and, after the sixth
# one, for the outcome of the calculation.
ANSWER_SECONDS = 3.0

HINT = "Enter Capturar | Esc Cancelar"
TITLE = "Calibrar acelerômetro"
KEEP_STILL = "Mantenha a placa parada"

STATUS_CAPTURING = "Capturando…"
STATUS_CALCULATING = "Calculando…"
STATUS_NO_ANSWER = "Sem resposta do inclinômetro"
STATUS_SAVED = "Calibração salva"
STATUS_INVALID = "Calibração inválida, repita as posições"
STATUS_NO_RESULT = "Sem resultado da calibração"

POSITION_NAMES = {
    "#KZU": "Eixo Z para cima",
    "#KZD": "Eixo Z para baixo",
    "#KXU": "Eixo X para cima",
    "#KXD": "Eixo X para baixo",
    "#KYU": "Eixo Y para cima",
    "#KYD": "Eixo Y para baixo",
}
STEPS = tuple((command, POSITION_NAMES[command]) for command in CALIBRATION_POSITIONS)


class Phase(enum.Enum):
    WAITING = "waiting"  # for Enter on the current step
    CAPTURING = "capturing"  # the capture command was sent; waiting for its acknowledgement
    CALCULATING = "calculating"  # the sixth capture was acknowledged; waiting for the outcome
    SAVED = "saved"
    INVALID = "invalid"  # also when no outcome arrived in time


class CloseReason(enum.Enum):
    CANCELLED = "cancelled"
    DISCONNECTED = "disconnected"
    DONE = "done"  # closed by the user after the outcome


class CalibrationWizard:
    """
    The six-position accelerometer calibration, one step at a time. It is driven by `confirm()` (Enter), `cancel()`
    (ESC) and `update()` (the screen's periodic refresh), and moves on only from what the device answered (the
    snapshot's calibration progress), never from having sent a command. It has no Qt in it: `gyro` only needs
    `capture(position)` and `snapshot()`.
    """

    def __init__(self, gyro, clock: Callable[[], float] = time.monotonic):
        self._gyro = gyro
        self._clock = clock
        self._step = 0
        self._phase = Phase.WAITING
        self._status = ""
        self._deadline = 0.0
        self._close_reason: Optional[CloseReason] = None

    # ── State (read by the screen and the tests) ─────────────────────────────

    @property
    def closed(self) -> bool:
        return self._close_reason is not None

    @property
    def close_reason(self) -> Optional[CloseReason]:
        return self._close_reason

    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def step_number(self) -> int:
        return self._step + 1

    @property
    def progress_text(self) -> str:
        return f"Passo {self.step_number} de {len(STEPS)}"

    @property
    def instruction_text(self) -> str:
        return f"{STEPS[self._step][1]}. {KEEP_STILL}"

    @property
    def status_text(self) -> str:
        return self._status

    # ── Keys ─────────────────────────────────────────────────────────────────

    def confirm(self):
        """Enter: capture the current position, restart after a bad outcome, or close after a good one."""
        if self.closed:
            return
        if self._phase is Phase.WAITING:
            self._capture()
        elif self._phase is Phase.INVALID:
            self._restart()
        elif self._phase is Phase.SAVED:
            self._close(CloseReason.DONE)

    def cancel(self):
        """ESC: close the wizard. Nothing is sent to undo what the device already captured."""
        if self.closed:
            return
        finished = self._phase in (Phase.SAVED, Phase.INVALID)
        self._close(CloseReason.DONE if finished else CloseReason.CANCELLED)

    # ── Device answers and time ──────────────────────────────────────────────

    def update(self, snapshot: Optional[GyroSnapshot] = None):
        """Follow the device: advance on an acknowledgement, time out, or close when the port is gone."""
        if self.closed:
            return
        snapshot = self._gyro.snapshot() if snapshot is None else snapshot
        if snapshot.status in (GyroStatus.DISABLED, GyroStatus.DISCONNECTED):
            self._close(CloseReason.DISCONNECTED)
            return
        progress = snapshot.calibration
        if self._phase is Phase.CAPTURING:
            last = self._step == len(STEPS) - 1
            # The outcome is accepted on the last step because the device sends it right after the sixth
            # acknowledgement, which it clears: a refresh between the two lines would otherwise miss it.
            if STEPS[self._step][0] in progress.acknowledged or (last and progress.outcome is not None):
                self._acknowledged(last)
            elif self._clock() >= self._deadline:
                self._phase, self._status = Phase.WAITING, STATUS_NO_ANSWER
        if self._phase is Phase.CALCULATING:
            if progress.outcome == OUTCOME_SAVED:
                self._phase, self._status = Phase.SAVED, STATUS_SAVED
            elif progress.outcome == OUTCOME_INVALID:
                self._phase, self._status = Phase.INVALID, STATUS_INVALID
            elif self._clock() >= self._deadline:
                self._phase, self._status = Phase.INVALID, STATUS_NO_RESULT

    # ── Internals ────────────────────────────────────────────────────────────

    def _capture(self):
        if not self._gyro.capture(STEPS[self._step][0]):
            self._close(CloseReason.DISCONNECTED)
            return
        self._phase, self._status = Phase.CAPTURING, STATUS_CAPTURING
        self._deadline = self._clock() + ANSWER_SECONDS

    def _acknowledged(self, last: bool):
        if last:
            self._phase, self._status = Phase.CALCULATING, STATUS_CALCULATING
            self._deadline = self._clock() + ANSWER_SECONDS
        else:
            self._step += 1
            self._phase, self._status = Phase.WAITING, ""

    def _restart(self):
        self._step = 0
        self._phase, self._status = Phase.WAITING, ""

    def _close(self, reason: CloseReason):
        self._close_reason = reason
