"""Shared test data and builders."""
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent

from app.masterinjection.signal import ParsedSignal, Signal

# A real combined frame taken from log_stream.csv (34 fields, positions 0..33).
SAMPLE_FRAME = (
    "#D01;3415;20;10;41;41;1119;107;6;638;39;0;1;1000;1101;0;0;"
    "#D02;141;360;327;543;347;86;0;1000;1009;1170;150;0;784;5000;0;4"
)

RPM_AXIS = [500, 750, 1000, 1250, 1500, 1750, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]
MAP_AXIS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160]


def frame_with(overrides: dict[int, str] | None = None, frame: str = SAMPLE_FRAME) -> str:
    """Return `frame` with the given {position: raw_text} replaced."""
    parts = frame.split(";")
    for position, raw in (overrides or {}).items():
        parts[position] = str(raw)
    return ";".join(parts)


def parsed(signal: Signal, value, raw=None) -> ParsedSignal:
    """Build a ParsedSignal without going through a frame."""
    return ParsedSignal(signal, value if raw is None else raw, value)


def key_press(key: Qt.Key, auto_repeat: bool = False) -> QKeyEvent:
    """A synthetic key press, optionally flagged as an OS auto-repeat."""
    return QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, "", auto_repeat, 1)
