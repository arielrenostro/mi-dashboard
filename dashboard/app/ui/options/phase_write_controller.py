import enum
import logging
from typing import Callable, List, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from app.masterinjection.protocol import (
    EcuCommand, EcuResponse, Phase, parse_x02, x02_phase, x02_with_phase,
)

logger = logging.getLogger(__name__)

WRITE_DELAY_MS = 1000
ANSWER_TIMEOUT_MS = 2000

STATUS_PENDING = "Alteração pendente…"
STATUS_SENDING = "Enviando para a ECU…"
STATUS_APPLIED = "Fase aplicada (não gravada na memória)"
STATUS_NO_ANSWER = "Sem resposta da ECU"
STATUS_INVALID = "Resposta #X02 inválida"


class _State(enum.Enum):
    IDLE = 0
    PENDING = 1     # toggled, waiting for the 1 s delay
    READING = 2     # #X02 requested, waiting for the block to modify
    VERIFYING = 3   # block written, #X02 requested again to confirm


class PhaseWriteController(QObject):
    """
    Sends a phase change to the ECU: read #X02, replace only the phase value, write the block back and
    read it again to confirm. The change is never persisted (no #D04).

    The ECU and the shared state are reached through callables so the controller can be tested without
    either: `send_command(cmd, args)` queues a command (args is None for a request), `get_block()` returns
    the last #X02 block published (or None) and `set_block(values)` publishes a new one. Lines from the ECU
    are fed to `on_line_received`. `on_written` (e.g. a confirmation sound) is called once each time the block is queued for writing. `changed` fires whenever the displayed phase or the status text changes.
    """

    changed = pyqtSignal()

    def __init__(self, send_command: Callable[[EcuCommand, Optional[List[int]]], None],
                 get_block: Callable[[], Optional[List[int]]],
                 set_block: Callable[[List[int]], None],
                 on_written: Optional[Callable[[], None]] = None,
                 parent=None):
        super().__init__(parent)
        self._send_command = send_command
        self._get_block = get_block
        self._set_block = set_block
        self._on_written = on_written

        self._state = _State.IDLE
        self._requested: Optional[Phase] = None
        self._status = ""

        self._delay_timer = QTimer()
        self._delay_timer.setSingleShot(True)
        self._delay_timer.timeout.connect(self._on_delay_elapsed)

        self._answer_timer = QTimer()
        self._answer_timer.setSingleShot(True)
        self._answer_timer.timeout.connect(self._on_answer_timeout)

    # ------------------------------------------------------------------ view

    @property
    def status(self) -> str:
        return self._status

    @property
    def in_progress(self) -> bool:
        return self._state is not _State.IDLE

    def published_phase(self) -> Optional[Phase]:
        """The phase of the last block published to the shared state."""
        return x02_phase(self._get_block())

    def displayed_phase(self) -> Optional[Phase]:
        """The requested phase while a change is in progress, otherwise the published one."""
        if self._state is not _State.IDLE:
            return self._requested
        return self.published_phase()

    def clear_success_status(self):
        """Forget the success message (used when the screen is left); failure messages stay."""
        if self._state is _State.IDLE and self._status == STATUS_APPLIED:
            self._status = ""
            self.changed.emit()

    # --------------------------------------------------------------- actions

    def request_refresh(self):
        """Ask the ECU for the block so the published phase is current. Writes nothing."""
        if self.in_progress:
            return
        self._send_command(EcuCommand.PARAMETERS_X02, None)

    def toggle(self):
        """Request the opposite of the displayed phase and (re)start the 1 s delay."""
        current = self.displayed_phase()
        if current is None:
            return
        self._answer_timer.stop()
        self._requested = current.opposite
        self._state = _State.PENDING
        self._status = STATUS_PENDING
        self._delay_timer.start(WRITE_DELAY_MS)
        self.changed.emit()

    def on_line_received(self, line: str):
        """Handle a line from the ECU; only `#X02` lines matter."""
        if not line.startswith(EcuResponse.PARAMETERS_X02.value):
            return
        block = parse_x02(line)
        waiting = self._state in (_State.READING, _State.VERIFYING)

        if block is None:
            logger.warning("Resposta #X02 inválida: %s", line)
            if waiting:
                self._fail(STATUS_INVALID)
            return

        self._set_block(block)

        if self._state is _State.READING:
            self._answer_timer.stop()
            self._write(block)
        elif self._state is _State.VERIFYING:
            self._answer_timer.stop()
            self._confirm(block)
        else:
            self.changed.emit()

    # -------------------------------------------------------------- sequence

    def _on_delay_elapsed(self):
        self._state = _State.READING
        self._status = STATUS_SENDING
        self._send_command(EcuCommand.PARAMETERS_X02, None)
        self._answer_timer.start(ANSWER_TIMEOUT_MS)
        self.changed.emit()

    def _write(self, block: List[int]):
        if x02_phase(block) == self._requested:
            self._finish(STATUS_APPLIED)
            return
        new_block = x02_with_phase(block, self._requested)
        logger.info("Gravando fase %s na ECU: %s", self._requested.label, new_block)
        self._send_command(EcuCommand.PARAMETERS_X02, new_block)
        if self._on_written is not None:
            self._on_written()
        self._send_command(EcuCommand.PARAMETERS_X02, None)
        self._state = _State.VERIFYING
        self._answer_timer.start(ANSWER_TIMEOUT_MS)
        self.changed.emit()

    def _confirm(self, block: List[int]):
        phase = x02_phase(block)
        if phase == self._requested:
            self._finish(STATUS_APPLIED)
        else:
            self._finish(f"A ECU manteve a fase {phase.label if phase is not None else '—'}")

    def _finish(self, status: str):
        self._state = _State.IDLE
        self._requested = None
        self._status = status
        self.changed.emit()

    def _fail(self, status: str):
        self._answer_timer.stop()
        self._finish(status)

    def _on_answer_timeout(self):
        if self._state in (_State.READING, _State.VERIFYING):
            logger.warning("Sem resposta da ECU ao #X02")
            self._fail(STATUS_NO_ANSWER)
