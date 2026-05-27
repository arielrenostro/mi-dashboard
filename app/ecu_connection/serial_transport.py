import logging
import threading

import serial

from app.ecu_connection.transport import EcuTransport

logger = logging.getLogger(__name__)


class SerialTransport(EcuTransport):
    """Transporte físico via porta serial usando pyserial."""

    def __init__(self, port: str, baudrate: int, timeout: float = 3.0):
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._serial: serial.Serial | None = None
        self._lock = threading.Lock()

    def connect(self) -> None:
        logger.info("SerialTransport: abrindo porta %s @ %d baud", self._port, self._baudrate)
        self._serial = serial.Serial(
            port=self._port,
            baudrate=self._baudrate,
            timeout=self._timeout,
        )
        logger.info("SerialTransport: porta %s aberta", self._port)

    def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
            logger.info("SerialTransport: porta %s fechada", self._port)
        self._serial = None

    def readline(self) -> str:
        if not self._serial or not self._serial.is_open:
            return ""
        raw = self._serial.readline()
        return raw.decode("utf-8", errors="replace").strip()

    def write(self, line: str) -> None:
        if not self._serial or not self._serial.is_open:
            raise IOError("SerialTransport: porta não está aberta")
        with self._lock:
            self._serial.write((line + "\n").encode("utf-8"))

    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open
