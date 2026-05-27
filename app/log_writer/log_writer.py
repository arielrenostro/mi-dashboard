import csv
import os
from datetime import datetime

from PyQt6.QtCore import QThread, QObject
from pyqtgraph.Qt.QtCore import Slot, Signal

from app.event.app_events import AppEventType, EcuMessFrameEvent
from app.event.bus import event_bus


class Worker(QObject):
    finished = Signal()

    def __init__(self, log_file):
        super().__init__()
        exists = os.path.exists(log_file)
        self.log_file = open(log_file, "a", newline='')
        self.csv_writer = csv.writer(self.log_file, delimiter=';', lineterminator='\n')
        if not exists:
            self.csv_writer.writerow(
                ["Timestamp", "Event", "Mess 1", "RPM", "MAP", "Boost", "Load %", "Idle", "Lambda 1", "Inj. Pulse",
                 "Inj. Utiliz.",
                 "VE Value", "Ign. Adv.", "Knock", "A/C Input", "Start Input", "Outputs 1", "Outputs 2", "Lambda 2",
                 "Mess 2", "Batt Volt.", "CLT", "IAT", "Inj. DT", "Ign. Dwell", "KM/H", "Lambda Loop", "Lambda Target",
                 "Lambda Corr", "Strobo Angle", "Turbo Target", "ACC %", "ACP %", "dACC %", "0", "0"])
            self.log_file.flush()

    @Slot(list)
    def process_task(self, data):
        self.csv_writer.writerow(data)
        self.log_file.flush()


class LogWriter(QObject):
    task = Signal(list)

    def __init__(self, log_file):
        super().__init__()
        self._event_pending = False
        self._pending: dict[str, str] = {}   # buffer por frame_id

        self.thread = QThread()
        self.worker = Worker(log_file)
        self.worker.moveToThread(self.thread)

        self.task.connect(self.worker.process_task)
        self.thread.start()

        # Inscrições no bus
        event_bus.subscribe(AppEventType.ECU_MESS_FRAME, self._on_mess_frame)
        event_bus.subscribe(AppEventType.EVENT_MARK_REQUESTED, lambda _: self.set_event_pending())

    def set_event_pending(self):
        self._event_pending = True

    def _on_mess_frame(self, event: EcuMessFrameEvent) -> None:
        self._pending[event.frame_id] = event.line

        if "D01" not in self._pending or "D02" not in self._pending:
            return

        d01_parts = self._pending["D01"].split(";")[1:]  # excluir "#D01"
        d02_parts = self._pending["D02"].split(";")[1:]  # excluir "#D02"

        timestamp = datetime.now().isoformat()
        event_flag = "MARK" if self._event_pending else ""
        self._event_pending = False

        row = [timestamp, event_flag] + d01_parts + d02_parts
        self.task.emit(row)
        self._pending.clear()
