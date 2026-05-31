import logging

import serial

from app.ecu_connection.transport import EcuTransport

logger = logging.getLogger(__name__)


class EcuTransportSerial(EcuTransport):

    def __init__(self, port: str, baudrate: int):
        self._serial = serial.Serial(baudrate=baudrate, timeout=1, write_timeout=1)
        self._serial.port = port

    def open(self) -> None:
        if not self._serial.is_open:
            logger.info("Opening serial port %s", self._serial.port)
            self._serial.open()
            logger.info("Serial port opened")

    def close(self) -> None:
        try:
            self._serial.close()
        except Exception:
            pass

    def is_open(self) -> bool:
        return self._serial.is_open

    def read_line(self) -> str:
        return self._serial.readline().decode("utf-8").strip()

    def write(self, data: bytes) -> None:
        self._serial.write(data)
