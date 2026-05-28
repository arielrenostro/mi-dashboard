from __future__ import annotations

import logging

import serial

from app.ecu.transport.base import EcuTransport

logger = logging.getLogger(__name__)


class SerialTransport(EcuTransport):

    def __init__(self, port: str, baudrate: int):
        self._port = port
        self._baudrate = baudrate
        self._serial = serial.Serial(baudrate=baudrate, timeout=0.05, write_timeout=1)
        self._serial.port = port

    def open(self) -> None:
        if not self._serial.is_open:
            logger.info("Abrindo porta serial %s @ %d", self._port, self._baudrate)
            self._serial.open()

    def close(self) -> None:
        try:
            if self._serial.is_open:
                self._serial.close()
        except Exception:
            pass

    def read_line(self) -> str:
        try:
            return self._serial.readline().decode("utf-8").strip()
        except Exception:
            return ""

    def write_line(self, line: str) -> None:
        self._serial.write(f"{line}\n".encode("utf-8"))

    def is_open(self) -> bool:
        return self._serial.is_open
