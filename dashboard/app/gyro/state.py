import enum
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from app.gyro.protocol import (
    CALIBRATION_POSITIONS, COMMAND_CALIBRATION_RESTORE, COMMAND_ZERO, GyroCalibrationReport, GyroCommandReply,
    GyroHeader, GyroMessage, GyroReading, MESSAGE_CALIBRATION_INVALID, MESSAGE_CALIBRATION_SAVED, STATUS_OK, parse_line)

# More than this without a valid data line (the device sends 100 per second) is "no signal".
NO_SIGNAL_SECONDS = 1.0


class GyroStatus(enum.Enum):
    DISABLED = "disabled"
    DISCONNECTED = "disconnected"
    NO_SIGNAL = "no signal"
    NOT_ZEROED = "not zeroed"
    USABLE = "usable"


OUTCOME_SAVED = "saved"
OUTCOME_INVALID = "invalid"


@dataclass(frozen=True)
class CalibrationProgress:
    """Where the accelerometer calibration stands, from the device's answers only."""
    acknowledged: frozenset = frozenset()  # capture commands the device answered OK since the last end of a run
    outcome: Optional[str] = None  # OUTCOME_SAVED / OUTCOME_INVALID of the latest run, None while it is open
    report: Optional[GyroCalibrationReport] = None  # the latest `#K;OFFSET;…` line


@dataclass(frozen=True)
class GyroSnapshot:
    status: GyroStatus
    pitch: Optional[float]  # only while USABLE
    reading: Optional[GyroReading]  # the latest valid data line, whatever the status
    message: str  # the latest `#M` text or command reply
    calibration: CalibrationProgress = CalibrationProgress()


class GyroState:
    """
    What the app knows about the inclinometer, thread safe. It stores no angle offset: the device applies the
    zero, and the app only tracks whether the device is zeroed, from the device's own answers. The derived
    status is computed from timestamps at the moment of the query, so a silent device is noticed even when
    nothing is arriving.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._lock = threading.RLock()
        self._enabled = False
        self._open = False
        self._reset_link()

    def _reset_link(self):
        self._opened_at: Optional[float] = None
        self._zeroed = False
        self._last_data_at: Optional[float] = None
        self._last_t_ms: Optional[float] = None
        self._reading: Optional[GyroReading] = None
        self._message = ""
        self._acknowledged: frozenset = frozenset()
        self._outcome: Optional[str] = None
        self._report: Optional[GyroCalibrationReport] = None

    # ── Port events ──────────────────────────────────────────────────────────

    def set_enabled(self, enabled: bool):
        """A port is configured (True) or not (False)."""
        with self._lock:
            self._enabled = enabled
            if not enabled:
                self._open = False
                self._reset_link()

    def opened(self):
        with self._lock:
            self._open = True
            self._reset_link()  # a new link never starts zeroed
            self._opened_at = self._clock()

    def closed(self):
        with self._lock:
            self._open = False
            self._reset_link()

    # ── Lines ────────────────────────────────────────────────────────────────

    def feed(self, line: str):
        """Apply one line received from the device. Lines that are not well-formed change nothing."""
        parsed = parse_line(line)
        if parsed is None:
            return
        with self._lock:
            now = self._clock()
            if isinstance(parsed, GyroReading):
                if self._last_t_ms is not None and parsed.t_ms < self._last_t_ms:
                    self._zeroed = False  # the clock went back: the device restarted and lost its zero
                self._last_t_ms = parsed.t_ms
                self._last_data_at = now
                self._reading = parsed
            elif isinstance(parsed, GyroHeader):
                self._zeroed = False  # sent once after the device starts
                self._last_t_ms = None
            elif isinstance(parsed, GyroMessage):
                self._apply_message(parsed.text)
            elif isinstance(parsed, GyroCommandReply):
                self._apply_reply(parsed)
            elif isinstance(parsed, GyroCalibrationReport):
                self._report = parsed

    def _apply_message(self, text: str):
        self._message = text  # free text: shown, and only the two calibration texts act on the state
        if text == MESSAGE_CALIBRATION_SAVED:
            self._end_calibration(OUTCOME_SAVED)
            self._zeroed = False  # the device keeps a zero taken with the old calibration
        elif text == MESSAGE_CALIBRATION_INVALID:
            self._end_calibration(OUTCOME_INVALID)

    def _end_calibration(self, outcome: str):
        self._acknowledged = frozenset()
        self._outcome = outcome

    def _apply_reply(self, reply: GyroCommandReply):
        self._message = reply.text
        if reply.status != STATUS_OK:
            return
        if reply.command == COMMAND_ZERO:
            self._zeroed = True
        elif reply.command in CALIBRATION_POSITIONS:
            self._acknowledged |= {reply.command}
            self._outcome = None
        elif reply.command == COMMAND_CALIBRATION_RESTORE:
            self._acknowledged = frozenset()
            self._outcome = None
            self._zeroed = False  # the restore changes the calibration the zero was taken with

    # ── Queries ──────────────────────────────────────────────────────────────

    def snapshot(self) -> GyroSnapshot:
        with self._lock:
            status = self._status(self._clock())
            pitch = self._reading.pitch if status is GyroStatus.USABLE else None
            calibration = CalibrationProgress(self._acknowledged, self._outcome, self._report)
            return GyroSnapshot(status, pitch, self._reading, self._message, calibration)

    def status(self) -> GyroStatus:
        with self._lock:
            return self._status(self._clock())

    def _status(self, now: float) -> GyroStatus:
        if not self._enabled:
            return GyroStatus.DISABLED
        if not self._open:
            return GyroStatus.DISCONNECTED
        reference = self._last_data_at if self._last_data_at is not None else self._opened_at
        if reference is None or now - reference > NO_SIGNAL_SECONDS:
            return GyroStatus.NO_SIGNAL
        if not self._zeroed:
            return GyroStatus.NOT_ZEROED
        if self._reading is None:
            return GyroStatus.NO_SIGNAL  # zeroed, but no data line has arrived since the port was opened
        return GyroStatus.USABLE
