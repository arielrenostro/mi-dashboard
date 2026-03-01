import sys

from PyQt6.QtWidgets import (
    QApplication
)

from app.alarm.alarm_worker import AlarmWorker
from app.dashboard.dashboard import Dashboard
from app.log_writer.log_writer import LogWriter
from app.reader.serial_reader_mock import SerialReaderMock

PORT = "COM1"
BAUDRATE = 115200
LOG_FILE = "log_stream.csv"
ALARM_SOUND = "alarm.wav"


# ==========================================
# MAIN
# ==========================================

def main():
    app = QApplication(sys.argv)

    alarm_worker = AlarmWorker(ALARM_SOUND)
    alarm_worker.start()

    dashboard = Dashboard(
        alarm_worker=alarm_worker,
    )
    log_writer = LogWriter(
        log_file=LOG_FILE,
    )

    serial_thread = SerialReaderMock(PORT, BAUDRATE)
    # serial_thread = SerialReader(PORT, BAUDRATE)
    serial_thread.emitter.connect(dashboard.process_line)
    serial_thread.emitter.connect(log_writer.write)
    serial_thread.start()

    app.exec()

    dashboard.close()
    alarm_worker.stop()
    serial_thread.stop()


if __name__ == "__main__":
    main()
