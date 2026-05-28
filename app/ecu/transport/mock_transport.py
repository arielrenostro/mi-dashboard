from __future__ import annotations

import logging
import time
from typing import Optional

from app.ecu.transport.base import EcuTransport

logger = logging.getLogger(__name__)

# Fixed breakpoints used by mock (mirrors EcuConnectionMock)
_MAP_BP = '#I21;20;30;40;50;60;70;80;90;100;120;140;160;180;200;220;240'
_RPM_BP = '#I20;400;800;1200;1600;2000;2400;2800;3200;3600;4000;4400;4800;5200;5600;6200;6800'

_VE_MAP = """\
#F16;855;898;909;896;918;926;934;962;974;994;1022;1020;1010;971;933;897
#F15;843;885;898;885;906;916;925;952;964;984;1012;1010;1000;961;924;888
#F14;832;874;884;874;893;906;916;943;954;974;1002;1000;990;951;915;879
#F13;822;863;873;861;881;896;907;934;945;964;992;990;980;942;906;871
#F12;810;851;861;848;868;886;889;916;926;945;973;972;962;924;888;854
#F11;792;832;842;829;847;865;868;896;909;928;958;948;939;903;868;835
#F10;774;813;822;810;826;846;845;860;870;888;924;915;906;870;836;804
#F09;748;785;795;782;805;820;813;812;811;839;873;881;872;838;806;775
#F08;733;770;778;768;785;800;789;789;790;814;838;846;838;806;775;745
#F07;710;745;753;747;745;768;761;757;758;790;813;821;810;777;747;720
#F06;695;730;737;726;713;736;738;733;739;773;787;795;787;756;726;698
#F05;633;665;690;692;685;727;702;695;714;753;764;771;763;733;705;678
#F04;566;594;651;647;656;703;678;668;681;730;747;753;746;718;690;663
#F03;561;569;623;622;618;669;650;636;653;681;701;708;701;673;647;622
#F02;568;587;635;626;635;672;631;612;631;679;710;714;707;678;651;625
#F01;561;588;630;636;615;632;597;588;621;667;697;701;694;666;640;615"""


class MockTransport(EcuTransport):
    """
    Replays a CSV log file, emitting D01 and D02 as separate read_line() calls.
    Precedes the log with synthetic handshake and VE map responses.
    """

    def __init__(self, mock_file: str):
        self._mock_file = mock_file
        self._queue: list[str] = []
        self._file = None
        self._last_timestamp: Optional[float] = None
        self._opened = False

    def open(self) -> None:
        self._opened = True
        self._queue = []
        self._last_timestamp = None

        # Synthetic handshake responses
        self._queue.append(_MAP_BP)
        self._queue.append(_RPM_BP)
        for line in _VE_MAP.strip().split("\n"):
            self._queue.append(line.strip())

        # Handshake echo
        self._queue.append("#D50;MockECU")
        self._queue.append("#D01;streaming_started")

        if self._file:
            try:
                self._file.close()
            except Exception:
                pass
        self._file = open(self._mock_file, "r")
        # Skip header line
        self._file.readline()

    def close(self) -> None:
        self._opened = False
        if self._file:
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None

    def read_line(self) -> str:
        if self._queue:
            return self._queue.pop(0)

        if not self._file:
            time.sleep(0.05)
            return ""

        raw = self._file.readline()
        if not raw:
            time.sleep(0.05)
            return ""

        parts = raw.replace(",", ";").strip().split(";")

        # Pace by timestamp delta
        if len(parts) > 0:
            try:
                ts_ms = int(parts[0])
                ts_s = ts_ms / 1000.0
                if self._last_timestamp is not None:
                    delta = ts_s - self._last_timestamp
                    if 0 < delta < 1.0:
                        time.sleep(delta)
                self._last_timestamp = ts_s
            except (ValueError, IndexError):
                time.sleep(0.1)

        # Reconstruct joined line and split into D01 / D02
        # CSV format: Timestamp;Event;#D01;...;#D02;...
        joined = ";".join(parts[2:])  # strip Timestamp + Event columns

        # Find D02 separator
        d02_idx = None
        tokens = joined.split(";")
        for i, t in enumerate(tokens):
            if t.startswith("#D02"):
                d02_idx = i
                break

        if d02_idx is not None:
            d01_line = ";".join(tokens[:d02_idx])
            d02_line = ";".join(tokens[d02_idx:])
            self._queue.append(d02_line)
            return d01_line
        else:
            return joined

    def write_line(self, line: str) -> None:
        pass  # mock — no-op

    def is_open(self) -> bool:
        return self._opened
