import sys
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication
)

from app.alarm.processor import AlarmProcessor
from app.dashboard.dashboard import Dashboard
from app.dashboard.grid import GRID, GRAPH
from app.event.key_hold_detector import KeyHoldDetector
from app.event.lambda_toggle import LambdaToggle
from app.event.marker import EventMarker
from app.log_writer.log_writer import LogWriter
from app.logger import setup_logging
from app.master.signal_processor import SignalProcessor
from app.ecu_connection.ecu_connection import EcuConnection
from app.ecu_connection.ecu_connection_mock import EcuConnectionMock
from app.vehicle.lambda_loop_state_processor import LambdaLoopStateProcessor
from app.vehicle.state import vehicle_state

PORT = "COM1"
BAUDRATE = 115200
LOG_FILE = f"C:\\Users\\ariel\\OneDrive\\Carros\\206\\Master Injection\\Datalogs\\dash\\log_stream_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
ALARM_SOUND = "alarm.wav"
EVENT_SOUND = "alarm.wav"
MOCK_FILE = "C:\\Users\\ariel\\OneDrive\\Carros\\206\\Master Injection\\Datalogs\\4Bar - 9\\log_stream_fixed.csv"

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

    if MOCK_FILE:
        ecu_connection = EcuConnectionMock(MOCK_FILE)
    else:
        ecu_connection = EcuConnection(PORT, BAUDRATE)

    lambda_loop_processor = LambdaLoopStateProcessor()

    lambda_toggle = LambdaToggle(EVENT_SOUND)
    lambda_toggle.command_requested.connect(ecu_connection.send_command)
    lambda_toggle.command_requested.connect(lambda_loop_processor.on_command_sent)

    space_detector = KeyHoldDetector(Qt.Key.Key_Space, 2000)
    space_detector.triggered.connect(lambda_toggle.handle_trigger)

    event_marker = EventMarker(EVENT_SOUND)
    event_marker.event_triggered.connect(log_writer.set_event_pending)

    dashboard.key_event.connect(event_marker.handle_key)
    dashboard.key_event.connect(space_detector.on_key_pressed)
    dashboard.key_released.connect(space_detector.on_key_released)

    signal_processor = SignalProcessor()
    signal_processor.emitter.connect(dashboard.process_signals)
    signal_processor.emitter.connect(alarm_processor.process_signals)
    signal_processor.emitter.connect(vehicle_state.update)
    signal_processor.emitter.connect(lambda_loop_processor.process_signals)

    ecu_connection.emitter.connect(signal_processor.process_line)
    ecu_connection.emitter.connect(log_writer.write)
    ecu_connection.start()

    app.exec()

    dashboard.close()
    alarm_processor.stop()
    ecu_connection.stop()


if __name__ == "__main__":
    main()
