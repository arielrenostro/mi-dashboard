from __future__ import annotations

from abc import ABC, abstractmethod


class EcuTransport(ABC):

    @abstractmethod
    def open(self) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def read_line(self) -> str:
        """Read one line. Returns empty string on timeout. Never raises on timeout."""
        pass

    @abstractmethod
    def write_line(self, line: str) -> None:
        """Write line + LF terminator encoded as UTF-8."""
        pass

    @abstractmethod
    def is_open(self) -> bool:
        pass
