import logging
import queue
import threading
import time
from collections.abc import Callable
from typing import Optional

import serial
from PyQt6.QtCore import QObject, pyqtSignal

from app.gyro.protocol import (
    BAUDRATE, CALIBRATION_POSITIONS, COMMAND_CALIBRATION_REPORT, COMMAND_CALIBRATION_RESTORE, COMMAND_ZERO)
from app.gyro.state import GyroState, GyroStatus

logger = logging.getLogger(__name__)

RETRY_SECONDS = 2.0
READ_TIMEOUT_SECONDS = 0.1


def open_serial(port: str):
    """115200 baud, 8 data bits, no parity, 1 stop bit; short timeouts so commands and a stop are never held up."""
    return serial.Serial(port, BAUDRATE, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                         stopbits=serial.STOPBITS_ONE, timeout=READ_TIMEOUT_SECONDS, write_timeout=1)


class GyroConnection(QObject):
    """
    The optional inclinometer. It opens `port` by itself, retries every 2 s while the port is configured but
    cannot be opened, and keeps `state` up to date from the lines it reads. Nothing here is reported through the
    ECU's error overlay. `step()` is one turn of the loop of the background thread (tests call it directly).
    """

    # Emitted when the status or the latest device message changes (never once per data line).
    state_changed = pyqtSignal()

    def __init__(self, port: str = "", serial_factory: Callable[[str], object] = open_serial,
                 clock: Callable[[], float] = time.monotonic, idle_wait: float = 0.05):
        super().__init__()
        self._serial_factory = serial_factory
        self._clock = clock
        self._idle_wait = idle_wait
        self.state = GyroState(clock)
        self._lock = threading.Lock()
        self._port = port
        self._user_closed = False
        self._serial = None
        self._open_port = ""
        self._next_try = 0.0
        self._commands: queue.Queue = queue.Queue()
        self._announced = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.state.set_enabled(bool(port))

    # ── Control (any thread) ─────────────────────────────────────────────────

    @property
    def port(self) -> str:
        return self._port

    def set_port(self, port: str):
        """Use another port ('' for none): the one in use is closed and the new one is opened right away."""
        with self._lock:
            self._port = port
            self._user_closed = False
            self._next_try = 0.0
        self.state.set_enabled(bool(port))

    def connect(self):
        """Open the port again after the user closed it."""
        with self._lock:
            self._user_closed = False
            self._next_try = 0.0

    def disconnect(self):
        """Close the port and keep it closed until `connect()` or another port."""
        with self._lock:
            self._user_closed = True

    def is_open(self) -> bool:
        return self.state.status() not in (GyroStatus.DISABLED, GyroStatus.DISCONNECTED)

    def is_user_closed(self) -> bool:
        return self._user_closed

    def snapshot(self):
        return self.state.snapshot()

    def zero(self) -> bool:
        """Ask the device to take the current position as flat. False when the port is not open."""
        return self._send(COMMAND_ZERO)

    def capture(self, position: str) -> bool:
        """Ask the device to capture one calibration position (one of CALIBRATION_POSITIONS). False when not sent."""
        if position not in CALIBRATION_POSITIONS:
            raise ValueError(f"Not a calibration position: {position!r}")
        return self._send(position)

    def request_calibration(self) -> bool:
        """Ask the device to report the calibration it uses. False when the port is not open."""
        return self._send(COMMAND_CALIBRATION_REPORT)

    def restore_calibration(self) -> bool:
        """Ask the device to go back to offset 0 and gain 1. False when the port is not open."""
        return self._send(COMMAND_CALIBRATION_RESTORE)

    def _send(self, command: str) -> bool:
        if not self.is_open():
            return False
        self._commands.put(command)
        return True

    # ── Thread ───────────────────────────────────────────────────────────────

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="gyro-connection", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 1.0):
        """Stop the thread (bounded wait) and close the port."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout)
            if thread.is_alive():
                logger.warning("The inclinometer thread did not finish within %.1f s", timeout)
        self._close()

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self.step()
            except Exception:
                logger.exception("Inclinometer loop failed")
                self._stop_event.wait(RETRY_SECONDS)
        self._close()

    def step(self):
        """One turn of the loop: apply port changes, open when due, read a line, write queued commands."""
        with self._lock:
            port, user_closed = self._port, self._user_closed
        if self._serial is not None and (user_closed or port != self._open_port):
            self._close()
        if self._serial is None:
            self._try_open(port, user_closed)
            if self._serial is None:
                self._announce()
                self._stop_event.wait(self._idle_wait)
                return
        self._read_and_write()
        self._announce()

    def _try_open(self, port: str, user_closed: bool):
        now = self._clock()
        if not port or user_closed or now < self._next_try:
            return
        try:
            opened = self._serial_factory(port)
        except Exception as error:
            logger.debug("Could not open the inclinometer port %s: %s", port, error)
            self._next_try = now + RETRY_SECONDS
            return
        self._serial = opened
        self._open_port = port
        self.state.opened()
        logger.info("Inclinometer connected on %s", port)

    def _read_and_write(self):
        try:
            raw = self._serial.readline()
            if raw:
                self.state.feed(raw.decode("utf-8", errors="replace"))
            self._write_commands()
        except Exception as error:
            logger.warning("Inclinometer connection lost: %s", error)
            self._close()
            self._next_try = self._clock() + RETRY_SECONDS

    def _write_commands(self):
        while True:
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                return
            logger.info("Sending %s to the inclinometer", command)
            self._serial.write(f"{command}\n".encode("utf-8"))

    def _close(self):
        port, self._serial = self._serial, None
        self._open_port = ""
        if port is not None:
            try:
                port.close()
            except Exception:
                logger.debug("Error while closing the inclinometer port", exc_info=True)
            self.state.closed()
        while not self._commands.empty():  # a command is never written to a port that comes later
            try:
                self._commands.get_nowait()
            except queue.Empty:
                break

    def _announce(self):
        snap = self.state.snapshot()
        key = (snap.status, snap.message, snap.calibration)
        if key != self._announced:
            self._announced = key
            self.state_changed.emit()
