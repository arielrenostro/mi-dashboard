import logging
import queue
import time

from app.ecu_connection.transport import EcuTransport

logger = logging.getLogger(__name__)

_DEFAULT_RPM_BREAKPOINTS = [500, 1000, 1500, 2000, 2500, 3000, 3500, 4000,
                             4500, 5000, 5500, 6000, 6500, 7000, 7500, 8000]
_DEFAULT_MAP_BREAKPOINTS = [20, 40, 60, 80, 100, 110, 120, 130,
                             140, 150, 155, 160, 165, 170, 180, 200]
_DEFAULT_VE_ROW = [800] * 16   # 80.0% para todas as células

_HARDCODED_VE = {
    "#F16": [855, 898, 909, 896, 918, 926, 934, 962, 974, 994, 1022, 1020, 1010, 971, 933, 897],
    "#F15": [843, 885, 898, 885, 906, 916, 925, 952, 964, 984, 1012, 1010, 1000, 961, 924, 888],
    "#F14": [832, 874, 884, 874, 893, 906, 916, 943, 954, 974, 1002, 1000, 990, 951, 915, 879],
    "#F13": [822, 863, 873, 861, 881, 896, 907, 934, 945, 964, 992, 990, 980, 942, 906, 871],
    "#F12": [810, 851, 861, 848, 868, 886, 889, 916, 926, 945, 973, 972, 962, 924, 888, 854],
    "#F11": [792, 832, 842, 829, 847, 865, 868, 896, 909, 928, 958, 948, 939, 903, 868, 835],
    "#F10": [774, 813, 822, 810, 826, 846, 845, 860, 870, 888, 924, 915, 906, 870, 836, 804],
    "#F09": [748, 785, 795, 782, 805, 820, 813, 812, 811, 839, 873, 881, 872, 838, 806, 775],
    "#F08": [733, 770, 778, 768, 785, 800, 789, 789, 790, 814, 838, 846, 838, 806, 775, 745],
    "#F07": [710, 745, 753, 747, 745, 768, 761, 757, 758, 790, 813, 821, 810, 777, 747, 720],
    "#F06": [695, 730, 737, 726, 713, 736, 738, 733, 739, 773, 787, 795, 787, 756, 726, 698],
    "#F05": [633, 665, 690, 692, 685, 727, 702, 695, 714, 753, 764, 771, 763, 733, 705, 678],
    "#F04": [566, 594, 651, 647, 656, 703, 678, 668, 681, 730, 747, 753, 746, 718, 690, 663],
    "#F03": [561, 569, 623, 622, 618, 669, 650, 636, 653, 681, 701, 708, 701, 673, 647, 622],
    "#F02": [568, 587, 635, 626, 635, 672, 631, 612, 631, 679, 710, 714, 707, 678, 651, 625],
    "#F01": [561, 588, 630, 636, 615, 632, 597, 588, 621, 667, 697, 701, 694, 666, 640, 615],
}


class MockTransport(EcuTransport):
    """Transporte mock que replaya um CSV de log e simula o protocolo de handshake.

    Durante o handshake, write() interpreta comandos e enfileira respostas em _line_queue.
    Durante streaming, linhas D01/D02 são enfileiradas por um thread interno de replay.
    readline() sempre consome de _line_queue.
    """

    def __init__(self, csv_file: str):
        self._csv_file = csv_file
        self._line_queue: queue.Queue = queue.Queue()
        self._csv_lines: list = []
        self._streaming = False
        self._connected = False
        self._replay_thread = None

    def connect(self) -> None:
        self._csv_lines = self._load_csv()
        self._line_queue = queue.Queue()
        self._streaming = False
        self._connected = True
        logger.info("MockTransport: conectado (CSV: %s, %d linhas)", self._csv_file, len(self._csv_lines))

    def disconnect(self) -> None:
        self._connected = False
        # Desbloquear readline() se estiver aguardando
        self._line_queue.put("")
        logger.info("MockTransport: desconectado")

    def readline(self) -> str:
        if not self._connected:
            return ""
        try:
            line = self._line_queue.get(timeout=3.0)
            return line
        except queue.Empty:
            return ""

    def write(self, line: str) -> None:
        """Interpreta o comando e enfileira resposta ou inicia streaming."""
        line = line.strip()
        logger.debug("MockTransport write: %s", line)

        if line == "#D50":
            self._line_queue.put("#D50;MockECU;v1.0")

        elif line == "#I20":
            bp_str = ";".join(str(v) for v in _DEFAULT_RPM_BREAKPOINTS)
            self._line_queue.put(f"#I20;{bp_str}")

        elif line == "#I21":
            bp_str = ";".join(str(v) for v in _DEFAULT_MAP_BREAKPOINTS)
            self._line_queue.put(f"#I21;{bp_str}")

        elif line.startswith("#F") and len(line) == 4:
            prefix = line  # e.g. "#F01"
            values = _HARDCODED_VE.get(prefix, _DEFAULT_VE_ROW)
            vals_str = ";".join(str(v) for v in values)
            self._line_queue.put(f"{prefix};{vals_str}")

        elif line == "#D01":
            # Inicio do streaming
            self._line_queue.put("#D01;OK")
            self._streaming = True
            self._start_replay_thread()
            logger.info("MockTransport: streaming iniciado")

        else:
            # Comandos fire-and-forget (#D04, #D05, #D06) — no-op
            logger.debug("MockTransport: comando ignorado: %s", line)

    def is_connected(self) -> bool:
        return self._connected

    def _start_replay_thread(self):
        """Inicia thread de replay do CSV que alimenta _line_queue."""
        import threading
        self._replay_thread = threading.Thread(target=self._replay_loop, daemon=True)
        self._replay_thread.start()

    def _replay_loop(self):
        """Loop de replay: enfileira linhas D01/D02 com timing do CSV."""
        if not self._csv_lines:
            return

        start_time = time.time()
        csv_start_ts = self._csv_lines[0][0]

        idx = 0
        while self._connected:
            if idx >= len(self._csv_lines):
                # Reinicia do início (loop)
                idx = 0
                start_time = time.time()
                csv_start_ts = self._csv_lines[0][0]

            ts, d01_line, d02_line = self._csv_lines[idx]

            # Calcular timing relativo
            elapsed_csv = (ts - csv_start_ts) / 1000.0  # ms → s
            elapsed_real = time.time() - start_time
            wait = elapsed_csv - elapsed_real
            if wait > 0:
                time.sleep(min(wait, 0.5))

            if not self._connected:
                break

            self._line_queue.put(d01_line)
            if d02_line is not None:
                self._line_queue.put(d02_line)

            idx += 1

    def _load_csv(self) -> list:
        """Carrega o CSV em memória. Retorna lista de (timestamp_ms, d01_line, d02_line_or_none)."""
        lines = []
        try:
            with open(self._csv_file, "r") as f:
                f.readline()  # skip header
                for raw_line in f:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    parts = raw_line.split(";")
                    if len(parts) < 3:
                        continue

                    # Format: Timestamp;Event;#D01;fields...;#D02;fields...
                    try:
                        ts = int(parts[0])
                    except (ValueError, IndexError):
                        continue

                    # Find D01 and D02 boundaries
                    try:
                        d01_idx = parts.index("#D01")
                    except ValueError:
                        continue

                    try:
                        d02_idx = parts.index("#D02", d01_idx)
                        d01_fields = parts[d01_idx:d02_idx]
                        d02_fields = parts[d02_idx:]
                        d01_line = ";".join(d01_fields)
                        d02_line = ";".join(d02_fields)
                    except ValueError:
                        d01_fields = parts[d01_idx:]
                        d01_line = ";".join(d01_fields)
                        d02_line = None

                    lines.append((ts, d01_line, d02_line))
        except Exception as e:
            logger.error("MockTransport: erro ao carregar CSV: %s", e)
        return lines
