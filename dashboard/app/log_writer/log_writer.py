import csv
import logging
import os
import time

from PyQt6.QtCore import QThread, QObject, Qt
from pyqtgraph.Qt.QtCore import Slot, Signal

from app.masterinjection.protocol import EcuResponse

logger = logging.getLogger(__name__)


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

    @Slot()
    def close(self):
        """Runs in the writer thread, after every row queued before it, then announces that it is done."""
        if not self.log_file.closed:
            self.log_file.flush()
            self.log_file.close()
        self.finished.emit()


class LogWriter(QObject):
    task = Signal(list)
    close_requested = Signal()

    def __init__(self, log_file):
        super().__init__()
        self._event_pending = False
        self._closed = False
        self.thread = QThread()
        self.worker = Worker(log_file)
        self.worker.moveToThread(self.thread)

        self.task.connect(self.worker.process_task)
        self.close_requested.connect(self.worker.close)
        # Direct: the worker thread ends itself. A queued call to the QThread object would need an event
        # loop in the main thread, which no longer runs during shutdown.
        self.worker.finished.connect(self.thread.quit, Qt.ConnectionType.DirectConnection)
        self.thread.start()

    def set_event_pending(self):
        self._event_pending = True

    def close(self, timeout_ms: int = 3000):
        """Write every row received so far, close the file and wait (bounded) for the writer thread."""
        if self._closed:
            return
        self._closed = True
        if not self.thread.isRunning():
            return
        self.close_requested.emit()  # queued behind the pending rows, so they are all written first
        if not self.thread.wait(timeout_ms):
            logger.warning("Datalog thread did not finish within %d ms; terminating it", timeout_ms)
            self.thread.terminate()
            self.thread.wait(1000)

    def write(self, line):
        if self._closed or not line.startswith(EcuResponse.MESS_DATA_1.value):
            return
        parts = line.split(";")
        if len(parts) < 2:
            return
        timestamp = int(time.time() * 1000)
        event = "MARK" if self._event_pending else ""
        self._event_pending = False
        self.task.emit([timestamp, event] + parts)
