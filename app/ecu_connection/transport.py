from abc import ABC, abstractmethod


class EcuTransport(ABC):
    """Pure I/O layer — knows nothing about the ECU protocol."""

    @abstractmethod
    def open(self) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def is_open(self) -> bool:
        pass

    @abstractmethod
    def read_line(self) -> str:
        """Blocking call. Returns one decoded, stripped line (no \\n)."""

    @abstractmethod
    def write(self, data: bytes) -> None:
        pass
