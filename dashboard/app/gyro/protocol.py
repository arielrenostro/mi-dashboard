"""The inclinometer's serial protocol (Arduino with an accelerometer, 115200 8N1): lines in, one command out."""
import math
from dataclasses import dataclass
from typing import Optional, Union

BAUDRATE = 115200

# The commands written to the device, each followed by "\n". (The gyroscope recalibration `#C` and the zero removal
# `#R` no longer exist.) The six capture commands are the accelerometer calibration positions in the order the
# wizard walks them; the device computes the calibration when the sixth distinct one is captured.
COMMAND_ZERO = "#Z"
CALIBRATION_POSITIONS = ("#KZU", "#KZD", "#KXU", "#KXD", "#KYU", "#KYD")
COMMAND_CALIBRATION_REPORT = "#KP"
COMMAND_CALIBRATION_RESTORE = "#KR"
COMMANDS = (COMMAND_ZERO, *CALIBRATION_POSITIONS, COMMAND_CALIBRATION_REPORT, COMMAND_CALIBRATION_RESTORE)

# Status of the command reply `#<CMD>;<STATUS>;` that changes the state, compared exactly (uppercase).
STATUS_OK = "OK"

# The `#M` texts that end a calibration (the only ones that act on the state).
MESSAGE_CALIBRATION_SAVED = "CALIBRACAO_SALVA"
MESSAGE_CALIBRATION_INVALID = "CALIBRACAO_INVALIDA_REPITA_AS_POSICOES"

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
    """A `#Z` or `#K…` line: the device's answer (ACK) to the command of the same name."""
    command: str  # with the '#', one of COMMANDS
    status: str

    @property
    def text(self) -> str:
        """How the Settings screen shows it: the command letter without the '#', a colon and the status."""
        return f"{self.command.lstrip('#')}: {self.status}"


@dataclass(frozen=True)
class GyroCalibrationReport:
    """The `#K;OFFSET;ox;oy;oz;SCALE;sx;sy;sz;` line: the accelerometer calibration the device uses (axes X, Y, Z)."""
    offset: tuple
    scale: tuple


GyroLine = Union[GyroReading, GyroHeader, GyroMessage, GyroCommandReply, GyroCalibrationReport]


def parse_line(line: str) -> Optional[GyroLine]:
    """
    Split at ';', drop the empty last item (every line ends with ';') and let the first item decide.
    Anything that is not a well-formed `#D`, `#H`, `#M`, command reply or `#K` report line gives None and never raises.
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
    if tag == "#K":
        return _parse_report(values)
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


def _parse_report(values: list) -> Optional[GyroCalibrationReport]:
    if len(values) != 8 or values[0] != "OFFSET" or values[4] != "SCALE":
        return None
    try:
        numbers = [float(v) for v in values[1:4] + values[5:8]]
    except ValueError:
        return None
    if not all(math.isfinite(n) for n in numbers):
        return None
    return GyroCalibrationReport(tuple(numbers[:3]), tuple(numbers[3:]))
