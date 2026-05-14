import sys
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication
)

from app.alarm.processor import AlarmProcessor
from app.dashboard.dashboard import Dashboard
from app.dashboard.grid import GRID, GRAPH
from app.event.marker import EventMarker
from app.log_writer.log_writer import LogWriter
from app.logger import setup_logging
from app.master.signal_processor import SignalProcessor
from app.reader.serial_reader import SerialReader
from app.reader.serial_reader_mock import SerialReaderMock
from app.vehicle.state import vehicle_state

PORT = "COM1"
BAUDRATE = 115200
LOG_FILE = f"C:\\Users\\ariel\\OneDrive\\Carros\\206\\Master Injection\\Datalogs\\dash\\log_stream_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
ALARM_SOUND = "alarm.wav"
EVENT_SOUND = "alarm.wav"
MOCK_FILE = "C:\\Users\\ariel\\OneDrive\\Carros\\206\\Master Injection\\Datalogs\\4Bar - 9\\log_stream_fixed.csv"
MOCK_FILE = False

# ==========================================
# MAIN
# ==========================================

def main():
    setup_logging()

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

    event_marker = EventMarker(EVENT_SOUND)
    dashboard.key_event.connect(event_marker.handle_key)
    event_marker.event_triggered.connect(log_writer.set_event_pending)

    signal_processor = SignalProcessor()
    signal_processor.emitter.connect(dashboard.process_signals)
    signal_processor.emitter.connect(alarm_processor.process_signals)
    signal_processor.emitter.connect(vehicle_state.update)

    if MOCK_FILE:
        serial_thread = SerialReaderMock(MOCK_FILE)
    else:
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
