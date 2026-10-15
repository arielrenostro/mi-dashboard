import re
from collections.abc import Callable
from typing import List, Optional

from serial.tools import list_ports


def _natural(name: str):
    """COM3 before COM10."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def list_serial_ports(provider: Optional[Callable[[], list]] = None) -> List[str]:
    """The serial ports the machine reports, by name and in ascending order. No port is opened."""
    ports = list_ports.comports() if provider is None else provider()
    return sorted((p.device for p in ports), key=_natural)
