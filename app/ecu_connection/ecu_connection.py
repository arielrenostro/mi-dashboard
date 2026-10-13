import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Any

from app.masterinjection.protocol import EcuCommand

logger = logging.getLogger(__name__)


class EcuConnectionStatus(Enum):
    CONNECTED = 0
    DISCONNECTED = 1
    CONNECTING = 2
    HANDSHAKE = 3
    ERROR = 4


class EcuConnection(ABC):

    def __init__(self):
        super().__init__()
        self.emitter = None
        self.error_emitter = None  # set by the thread wrapper; the mock never uses it
        self.running = False
        self._last_reported_error = None

    def report_error(self, message: str) -> None:
        """Tell the UI about a connection error, once: an identical message is not repeated until another one
        is reported or clear_reported_error() is called (when the connection recovers)."""
        if message == self._last_reported_error:
            return
        self._last_reported_error = message
        if self.error_emitter is not None:
            self.error_emitter.emit(message)

    def clear_reported_error(self) -> None:
        self._last_reported_error = None

    @abstractmethod
    def send_command(self, cmd: EcuCommand, args: List[Any] | None = None) -> None:
        pass

    @abstractmethod
    def run(self):
        pass

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    @abstractmethod
    def is_connected(self) -> bool:
        pass

    def get_connection_status(self) -> EcuConnectionStatus:
        pass
