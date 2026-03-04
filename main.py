import sys

from PyQt6.QtWidgets import (
    QApplication
)

from app.alarm.processor import AlarmProcessor
from app.dashboard.dashboard import Dashboard
from app.dashboard.grid import GRID, GRAPH
from app.log_writer.log_writer import LogWriter
from app.master.signal_processor import SignalProcessor
from app.reader.serial_reader import SerialReader
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

    dashboard = Dashboard(
        grid=GRID,
        graphs=GRAPH,
        graph_x_size=150,
    )
    log_writer = LogWriter(
        log_file=LOG_FILE,
    )

    alarm_processor = AlarmProcessor(ALARM_SOUND)
    alarm_processor.emitter.connect(dashboard.fire_field_alarm)
    alarm_processor.start()

    signal_processor = SignalProcessor()
    signal_processor.emitter.connect(dashboard.process_signals)
    signal_processor.emitter.connect(alarm_processor.process_signals)

    # serial_thread = SerialReaderMock(PORT, BAUDRATE)
    serial_thread = SerialReader(PORT, BAUDRATE)
    serial_thread.emitter.connect(signal_processor.process_line)
    serial_thread.emitter.connect(log_writer.write)
    serial_thread.start()

    app.exec()

    dashboard.close()
    alarm_processor.stop()
    serial_thread.stop()


if __name__ == "__main__":
    main()
