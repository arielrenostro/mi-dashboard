import logging
import time
from collections import deque
from typing import Deque

from app.ecu_connection.transport import EcuTransport

logger = logging.getLogger(__name__)

# Default VE map used for GET responses (row 1..16 → values)
_VE_DATA: dict[int, list[int]] = {
    1:  [561, 588, 630, 636, 615, 632, 597, 588, 621, 667, 697, 701, 694, 666, 640, 615],
    2:  [568, 587, 635, 626, 635, 672, 631, 612, 631, 679, 710, 714, 707, 678, 651, 625],
    3:  [561, 569, 623, 622, 618, 669, 650, 636, 653, 681, 701, 708, 701, 673, 647, 622],
    4:  [566, 594, 651, 647, 656, 703, 678, 668, 681, 730, 747, 753, 746, 718, 690, 663],
    5:  [633, 665, 690, 692, 685, 727, 702, 695, 714, 753, 764, 771, 763, 733, 705, 678],
    6:  [695, 730, 737, 726, 713, 736, 738, 733, 739, 773, 787, 795, 787, 756, 726, 698],
    7:  [710, 745, 753, 747, 745, 768, 761, 757, 758, 790, 813, 821, 810, 777, 747, 720],
    8:  [733, 770, 778, 768, 785, 800, 789, 789, 790, 814, 838, 846, 838, 806, 775, 745],
    9:  [748, 785, 795, 782, 805, 820, 813, 812, 811, 839, 873, 881, 872, 838, 806, 775],
    10: [774, 813, 822, 810, 826, 846, 845, 860, 870, 888, 924, 915, 906, 870, 836, 804],
    11: [792, 832, 842, 829, 847, 865, 868, 896, 909, 928, 958, 948, 939, 903, 868, 835],
    12: [810, 851, 861, 848, 868, 886, 889, 916, 926, 945, 973, 972, 962, 924, 888, 854],
    13: [822, 863, 873, 861, 881, 896, 907, 934, 945, 964, 992, 990, 980, 942, 906, 871],
    14: [832, 874, 884, 874, 893, 906, 916, 943, 954, 974, 1002, 1000, 990, 951, 915, 879],
    15: [843, 885, 898, 885, 906, 916, 925, 952, 964, 984, 1012, 1010, 1000, 961, 924, 888],
    16: [855, 898, 909, 896, 918, 926, 934, 962, 974, 994, 1022, 1020, 1010, 971, 933, 897],
}

_MAP_BREAKPOINTS = [20, 30, 40, 50, 60, 70, 80, 90, 100, 120, 140, 160, 180, 200, 220, 240]
_RPM_BREAKPOINTS = [400, 800, 1200, 1600, 2000, 2400, 2800, 3200, 3600, 4000, 4400, 4800, 5200, 5600, 6200, 6800]


class EcuTransportMock(EcuTransport):
    """
    Replays a CSV log file produced by LogWriter.
    write() generates appropriate protocol responses.
    read_line() drains response queue first, then replays the log file.
    """

    # Number of D01 values in the joined frame (before #D02 marker)
    _D01_VALUE_COUNT = 16

    def __init__(self, mock_file: str):
        self._mock_file = mock_file
        self._response_queue: Deque[str] = deque()
        self._frame_buffer: Deque[str] = deque()
        self._file = None
        self._streaming = False
        self._open = False
        self._last_timestamp: int | None = None
        self._log_format: str = "unknown"

    def open(self) -> None:
        self._file = open(self._mock_file, 'r')
        self._streaming = False
        self._open = True
        self._last_timestamp = None
        self._response_queue.clear()
        self._frame_buffer.clear()
        # Peek at first line to detect format
        first_line = self._file.readline().replace(',', ';').strip()
        parts = first_line.split(';')
        if len(parts) > 2 and parts[2] == "Mess 1":
            self._log_format = "this"
        elif parts[0] == "Mess 1":
            self._log_format = "master"
        else:
            self._log_format = "this"  # assume our format; header line already consumed
        i = 0
        while i < 1000:
            self._file.readline()
            i += 1
        logger.info("Mock transport opened, format: %s", self._log_format)

    def close(self) -> None:
        self._open = False
        self._streaming = False
        if self._file:
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None

    def is_open(self) -> bool:
        return self._open

    def write(self, data: bytes) -> None:
        cmd = data.decode("utf-8").strip()
        logger.debug("Mock write: %s", cmd)

        if cmd == "#D50":
            self._response_queue.append("#D50;MockECU;1.0")

        elif cmd == "#I21":
            vals = ";".join(str(v) for v in _MAP_BREAKPOINTS)
            self._response_queue.append(f"#I21;{vals}")

        elif cmd == "#I20":
            vals = ";".join(str(v) for v in _RPM_BREAKPOINTS)
            self._response_queue.append(f"#I20;{vals}")

        elif cmd.startswith("#F") and ";" not in cmd:
            # GET VE row: "#F01" → "#F01;v1;...;v16"
            try:
                row_num = int(cmd[2:])
                ve_vals = _VE_DATA.get(row_num, [700] * 16)
                vals = ";".join(str(v) for v in ve_vals)
                self._response_queue.append(f"{cmd};{vals}")
            except ValueError:
                pass

        elif cmd.startswith("#F") and ";" in cmd:
            # SET VE row: echo back
            self._response_queue.append(cmd)

        elif cmd == "#D01":
            # STREAMING_START ack — first #D01 frame from log acts as ack
            self._response_queue.append("#D01;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0")
            self._streaming = True

        elif cmd == "#D05":
            self._response_queue.append("#D05;closed")

        elif cmd == "#D06":
            self._response_queue.append("#D06;open")

        else:
            logger.debug("Mock: no response for command %s", cmd)

    def read_line(self) -> str:
        # Priority 1: responses to commands
        if self._response_queue:
            return self._response_queue.popleft()

        # Priority 2: buffered D02 from previous log line
        if self._frame_buffer:
            return self._frame_buffer.popleft()

        # Priority 3: read from log file when streaming
        if self._streaming and self._file:
            line = self._read_next_frame()
            if line:
                return line

        time.sleep(0.01)
        return ""

    def _read_next_frame(self) -> str:
        if not self._file:
            return ""

        while True:
            raw = self._file.readline()
            if not raw:
                logger.info("Mock: log file exhausted")
                self._streaming = False
                return ""

            raw = raw.replace(',', ';').strip()
            if not raw:
                continue

            parts = raw.split(';')

            d01 = ""
            d02 = ""
            if self._log_format == "this":
                # timestamp;event;#D01;v1..v16;#D02;w1..wN
                if len(parts) > 19 and parts[2] == "#D01" and parts[19] == "#D02":
                    d01 = ";".join(parts[2:19])   # "#D01;v1;...;v16"
                    d02 = ";".join(parts[19:])     # "#D02;w1;...;wN"
            else:
                if parts[0] == "#D01" and parts[17] == "#D02":
                    d01 = ";".join(parts[:17])  # "#D01;v1;...;v16"
                    d02 = ";".join(parts[17:])  # "#D02;w1;...;wN"

            self._frame_buffer.append(d02)
            self._pace(parts[0])
            return d01

    def _pace(self, timestamp_str: str) -> None:
        try:
            ts = int(timestamp_str)
            if self._last_timestamp is not None:
                diff_ms = ts - self._last_timestamp
                if 0 < diff_ms < 1000:
                    time.sleep(diff_ms / 1000.0)
            self._last_timestamp = ts
        except (ValueError, TypeError):
            time.sleep(0.1)
