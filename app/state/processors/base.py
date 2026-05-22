from abc import ABC, abstractmethod
from typing import List, Any, Dict

from PyQt6.QtCore import QObject

from app.masterinjection.protocol import EcuCommand
from app.masterinjection.signal import Signal, ParsedSignal


class Processor(ABC, QObject):

    def __init__(self):
        super().__init__()

    @abstractmethod
    def on_command_received(self, cmd: EcuCommand, args: List[Any]) -> None:
        pass

    @abstractmethod
    def on_signal_received(self, signals: Dict[Signal, ParsedSignal]) -> None:
        pass
