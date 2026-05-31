import csv
import os
import time

from PyQt6.QtCore import QThread, QObject
from pyqtgraph.Qt.QtCore import Slot, Signal

from app.event.app_events import AppEventType, EcuFrameReceivedEvent, EcuFrameType
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
        self.thread = QThread()
        self.worker = Worker(log_file)
        self.worker.moveToThread(self.thread)

        self.task.connect(self.worker.process_task)
        self.thread.start()

        event_bus.subscribe(AppEventType.ECU_FRAME_RECEIVED, self._on_frame_received)

    def set_event_pending(self):
        self._event_pending = True

    def _on_frame_received(self, event: EcuFrameReceivedEvent) -> None:
        if event.frame_type != EcuFrameType.D01:
            return
        timestamp = int(time.time() * 1000)
        event_label = "MARK" if self._event_pending else ""
        self._event_pending = False
        # Reconstruct the D01 line: ["#D01"] + values
        parts = ["#D01"] + list(event.values)
        self.task.emit([timestamp, event_label] + parts)
