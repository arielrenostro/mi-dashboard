"""The inclinometer's serial protocol (Arduino with an MPU-6500, 115200 8N1): lines in, two commands out."""
import math
from dataclasses import dataclass
from typing import Optional, Union

BAUDRATE = 115200

# Commands written to the device, each followed by "\n". The app never sends "#R" (remove the zero).
COMMAND_ZERO = "#Z"
COMMAND_CALIBRATE = "#C"

# Texts of the `#M` messages that change the state, compared exactly.
MESSAGE_ZERO_SET = "Zero definido"
MESSAGE_ZERO_REMOVED = "Zero removido"
MESSAGE_CALIBRATING = "Calibrando..."
MESSAGE_CALIBRATION_OK = "Calibracao ok"

_DATA_FIELDS = ("t_ms", "pitch", "roll", "ax_g", "ay_g", "az_g", "gx_dps", "gy_dps", "gz_dps", "temp_c")


@dataclass(frozen=True)
class GyroReading:
    """One `#D` line. Pitch and roll are degrees with the device's zero already applied."""
    t_ms: float
    pitch: float  # positive = nose down
    roll: float  # positive = right side down
    ax_g: float
    ay_g: float
    az_g: float
    gx_dps: float
    gy_dps: float
    gz_dps: float
    temp_c: float


@dataclass(frozen=True)
class GyroHeader:
    """The `#H` line the device sends once after it starts."""


@dataclass(frozen=True)
class GyroMessage:
    """A `#M` line: free text about an event (boot, command answers, errors)."""
    text: str


GyroLine = Union[GyroReading, GyroHeader, GyroMessage]


def parse_line(line: str) -> Optional[GyroLine]:
    """
    Split at ';', drop the empty last item (every line ends with ';') and let the first item decide.
    Anything that is not a well-formed `#D`, `#H` or `#M` line gives None and never raises.
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
    return None


def _parse_data(values: list) -> Optional[GyroReading]:
    if len(values) != len(_DATA_FIELDS):
        return None
    try:
        numbers = [float(v) for v in values]
    except ValueError:
        return None
    if not all(math.isfinite(n) for n in numbers):
        return None
    return GyroReading(*numbers)
