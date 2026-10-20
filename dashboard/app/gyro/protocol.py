"""The inclinometer's serial protocol (Arduino with an accelerometer, 115200 8N1): lines in, one command out."""
import math
from dataclasses import dataclass
from typing import Optional, Union

BAUDRATE = 115200

# The only command written to the device, followed by "\n". (The gyroscope recalibration `#C` and the zero removal
# `#R` no longer exist; the accelerometer calibration `#K...` is made on the bench with a serial terminal.)
COMMAND_ZERO = "#Z"
COMMANDS = (COMMAND_ZERO,)

# Status of the command reply `#<CMD>;<STATUS>;` that changes the state, compared exactly (uppercase).
STATUS_OK = "OK"

DATA_FIELDS = ("t_ms", "pitch", "roll", "ax_g", "ay_g", "az_g", "temp_c")


@dataclass(frozen=True)
class GyroReading:
    """One `#D` line. Pitch and roll are degrees with the device's zero already applied."""
    t_ms: float
    pitch: float  # positive = nose down
    roll: float  # positive = right side down
    ax_g: float
    ay_g: float
    az_g: float
    temp_c: float


@dataclass(frozen=True)
class GyroHeader:
    """The `#H` line the device sends once after it starts."""


@dataclass(frozen=True)
class GyroMessage:
    """A `#M` line: free text about an event (boot, command answers, errors)."""
    text: str


@dataclass(frozen=True)
class GyroCommandReply:
    """A `#Z` line: the device's answer (ACK) to the command of the same name."""
    command: str  # with the '#', one of COMMANDS
    status: str

    @property
    def text(self) -> str:
        """How the Settings screen shows it: the command letter without the '#', a colon and the status."""
        return f"{self.command.lstrip('#')}: {self.status}"


GyroLine = Union[GyroReading, GyroHeader, GyroMessage, GyroCommandReply]


def parse_line(line: str) -> Optional[GyroLine]:
    """
    Split at ';', drop the empty last item (every line ends with ';') and let the first item decide.
    Anything that is not a well-formed `#D`, `#H`, `#M` or `#Z` reply line gives None and never raises.
    """
    items = line.rstrip("\r\n").split(";")
    if items and items[-1] == "":
        items.pop()
    if not items:
        return None
    tag, values = items[0], items[1:]
    if tag == "#D":
        return _parse_data(values)
    if tag == "#H":
        return GyroHeader()
    if tag == "#M":
        return GyroMessage(";".join(values))
    if tag in COMMANDS:
        return GyroCommandReply(tag, values[0]) if len(values) == 1 and values[0] else None
    return None


def _parse_data(values: list) -> Optional[GyroReading]:
    if len(values) != len(DATA_FIELDS):
        return None
    try:
        numbers = [float(v) for v in values]
    except ValueError:
        return None
    if not all(math.isfinite(n) for n in numbers):
        return None
    return GyroReading(*numbers)
