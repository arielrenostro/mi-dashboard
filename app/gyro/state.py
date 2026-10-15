import enum
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from app.gyro.protocol import (
    GyroHeader, GyroMessage, GyroReading, MESSAGE_CALIBRATING, MESSAGE_CALIBRATION_OK, MESSAGE_ZERO_REMOVED,
    MESSAGE_ZERO_SET, parse_line,
)

# More than this without a valid data line (the device sends 100 per second) is "no signal".
NO_SIGNAL_SECONDS = 1.0
# The device stops streaming while it recalibrates (about 2 s); after this long without `Calibracao ok` the app gives up.
CALIBRATION_SECONDS = 10.0


class GyroStatus(enum.Enum):
    DISABLED = "disabled"
    DISCONNECTED = "disconnected"
    CALIBRATING = "calibrating"
    NO_SIGNAL = "no signal"
    NOT_ZEROED = "not zeroed"
    USABLE = "usable"


@dataclass(frozen=True)
class GyroSnapshot:
    status: GyroStatus
    pitch: Optional[float]  # only while USABLE
    reading: Optional[GyroReading]  # the latest valid data line, whatever the status
    message: str  # the latest `#M` text


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
        self._calibrating_since: Optional[float] = None
        self._last_data_at: Optional[float] = None
        self._last_t_ms: Optional[float] = None
        self._reading: Optional[GyroReading] = None
        self._message = ""

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
                self._calibrating_since = None
                self._last_t_ms = None
            elif isinstance(parsed, GyroMessage):
                self._apply_message(parsed.text, now)

    def _apply_message(self, text: str, now: float):
        self._message = text
        if text == MESSAGE_ZERO_SET:
            self._zeroed = True
        elif text == MESSAGE_ZERO_REMOVED:
            self._zeroed = False
        elif text == MESSAGE_CALIBRATING:
            self._zeroed = False
            self._calibrating_since = now
        elif text == MESSAGE_CALIBRATION_OK:
            self._calibrating_since = None  # the zero is not assumed to survive: the user zeroes again

    # ── Queries ──────────────────────────────────────────────────────────────

    def snapshot(self) -> GyroSnapshot:
        with self._lock:
            status = self._status(self._clock())
            pitch = self._reading.pitch if status is GyroStatus.USABLE else None
            return GyroSnapshot(status, pitch, self._reading, self._message)

    def status(self) -> GyroStatus:
        with self._lock:
            return self._status(self._clock())

    def _status(self, now: float) -> GyroStatus:
        if not self._enabled:
            return GyroStatus.DISABLED
        if not self._open:
            return GyroStatus.DISCONNECTED
        if self._calibrating_since is not None and now - self._calibrating_since <= CALIBRATION_SECONDS:
            return GyroStatus.CALIBRATING
        reference = self._last_data_at if self._last_data_at is not None else self._opened_at
        if reference is None or now - reference > NO_SIGNAL_SECONDS:
            return GyroStatus.NO_SIGNAL
        if not self._zeroed:
            return GyroStatus.NOT_ZEROED
        if self._reading is None:
            return GyroStatus.NO_SIGNAL  # zeroed, but no data line has arrived since the port was opened
        return GyroStatus.USABLE
