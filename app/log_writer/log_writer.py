from __future__ import annotations

import csv
import os
import threading
import time

from PyQt6.QtCore import QThread, QObject, QTimer
from pyqtgraph.Qt.QtCore import Slot, Signal

from app.event.app_events import AppEventType, EcuMessFrameEvent


class Worker(QObject):
    finished = Signal()

    def __init__(self, log_file):
        super().__init__()
        exists = os.path.exists(log_file)
        self.log_file = open(log_file, "a", newline="")
        self.csv_writer = csv.writer(self.log_file, delimiter=";", lineterminator="\n")
        if not exists:
            self.csv_writer.writerow(
                ["Timestamp", "Event", "Mess 1", "RPM", "MAP", "Boost", "Load %", "Idle",
                 "Lambda 1", "Inj. Pulse", "Inj. Utiliz.", "VE Value", "Ign. Adv.", "Knock",
                 "A/C Input", "Start Input", "Outputs 1", "Outputs 2", "Lambda 2",
                 "Mess 2", "Batt Volt.", "CLT", "IAT", "Inj. DT", "Ign. Dwell", "KM/H",
                 "Lambda Loop", "Lambda Target", "Lambda Corr", "Strobo Angle",
                 "Turbo Target", "ACC %", "ACP %", "dACC %", "0", "0"]
            )
            self.log_file.flush()

        # Accumulator for D01+D02 pairing
        self._d01: list | None = None
        self._d02: list | None = None
        self._d01_timestamp: float = 0.0
        self._partial_timer: QTimer | None = None
        self._event_pending = False
        self._lock = threading.Lock()

    def set_event_pending(self):
        with self._lock:
            self._event_pending = True

    @Slot(list)
    def process_task(self, data):
        self.csv_writer.writerow(data)
        self.log_file.flush()

    @Slot(str, str)
    def on_mess_frame(self, frame_type: str, line: str) -> None:
        if frame_type == "D03":
            return

        with self._lock:
            if frame_type == "D01":
                self._d01 = line.split(";")
                self._d01_timestamp = time.time()
                self._d02 = None
                # Start partial-row timer
                if self._partial_timer:
                    self._partial_timer.stop()
                self._partial_timer = QTimer()
                self._partial_timer.setSingleShot(True)
                self._partial_timer.timeout.connect(self._flush_partial)
                self._partial_timer.start(500)

            elif frame_type == "D02":
                self._d02 = line.split(";")
                if self._partial_timer:
                    self._partial_timer.stop()
                    self._partial_timer = None
                if self._d01 is not None:
                    self._write_row(partial=False)

    def _flush_partial(self):
        with self._lock:
            if self._d01 is not None and self._d02 is None:
                self._write_row(partial=True)

    def _write_row(self, partial: bool) -> None:
        timestamp = int(time.time() * 1000)
        if self._event_pending:
            event = "MARK"
            self._event_pending = False
        elif partial:
            event = "PARTIAL"
        else:
            event = ""

        d01_parts = self._d01 or []
        d02_parts = self._d02 or []

        row = [timestamp, event] + d01_parts + d02_parts
        self.csv_writer.writerow(row)
        self.log_file.flush()

        self._d01 = None
        self._d02 = None


class LogWriter(QObject):
    _frame_signal = Signal(str, str)
    task = Signal(list)

    def __init__(self, log_file):
        super().__init__()
        self._thread = QThread()
        self._worker = Worker(log_file)
        self._worker.moveToThread(self._thread)

        self.task.connect(self._worker.process_task)
        self._frame_signal.connect(self._worker.on_mess_frame)
        self._thread.start()

        from app.event.bus import event_bus
        event_bus.subscribe(AppEventType.ECU_MESS_FRAME, self._on_mess_frame)

    def _on_mess_frame(self, event: EcuMessFrameEvent) -> None:
        self._frame_signal.emit(event.frame_type, event.line)

    def set_event_pending(self) -> None:
        self._worker.set_event_pending()

    # Legacy write() kept for compatibility during migration
    def write(self, line: str) -> None:
        pass
