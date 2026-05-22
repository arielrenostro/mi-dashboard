import logging
from abc import ABC, abstractmethod
from typing import List, Any

from app.masterinjection.protocol import EcuCommand

logger = logging.getLogger(__name__)


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

    @abstractmethod
    def stop(self):
        pass
