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
        self.running = False

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
