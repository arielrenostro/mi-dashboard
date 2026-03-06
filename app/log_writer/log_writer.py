import csv
import os
import time

from PyQt6.QtCore import QThread, QObject
from PyQt6.QtWidgets import QWidget
from pyqtgraph.Qt.QtCore import Slot, Signal

from app.master.log import LOG_PREFIX


class Worker(QObject):
    finished = Signal()

    def __init__(self, log_file):
        super().__init__()
        exists = os.path.exists(log_file)
        self.log_file = open(log_file, "a", newline='')
        self.csv_writer = csv.writer(self.log_file, delimiter=';', lineterminator='\n')
        if not exists:
            self.csv_writer.writerow(
                ["Timestamp", "Mess 1", "RPM", "MAP", "Boost", "Load %", "Idle", "Lambda 1", "Inj. Pulse", "Inj. Utiliz.",
                 "VE Value", "Ign. Adv.", "Knock", "A/C Input", "Start Input", "Outputs 1", "Outputs 2", "Lambda 2",
                 "Mess 2", "Batt Volt.", "CLT", "IAT", "Inj. DT", "Ign. Dwell", "KM/H", "Lambda Loop", "Lambda Target",
                 "Lambda Corr", "Strobo Angle", "Turbo Target", "ACC %", "ACP %", "dACC %", "0", "0"])
            self.log_file.flush()

    @Slot(list)
    def process_task(self, data):
        self.csv_writer.writerow(data)
        self.log_file.flush()


class LogWriter(QWidget):
    task = Signal(list)

    def __init__(self, log_file):
        super().__init__()
        self.thread = QThread()
        self.worker = Worker(log_file)
        self.worker.moveToThread(self.thread)

        self.task.connect(self.worker.process_task)
        self.thread.start()

    def write(self, line):
        if not line.startswith(LOG_PREFIX):
            return
        parts = line.split(";")
        if len(parts) < 2:
            return
        timestamp = int(time.time() * 1000)
        self.task.emit([timestamp] + parts)
