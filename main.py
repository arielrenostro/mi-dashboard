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
from app.master.ecu import EcuCommand
from app.master.signal_processor import SignalProcessor
from app.ecu_connection.ecu_connection import EcuConnection
from app.ecu_connection.ecu_connection_mock import EcuConnectionMock
from app.screen.app_window import AppWindow
from app.screen.home_screen import HomeScreen
from app.ve_calibration.ve_calibration_screen import VeCalibrationScreen
from app.ve_calibration.ve_map_state import ve_map_state
from app.ve_calibration.ve_write_controller import VeWriteController
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

    app_window = AppWindow()

    dashboard = Dashboard(
        grid=GRID,
        graphs=GRAPH,
        graph_x_size=150,
    )

    home_screen = HomeScreen()

    ve_calibration_screen = VeCalibrationScreen()
    ve_calibration_screen.populate_ve_table(
        ve_map_state.rpm_axis,
        ve_map_state.map_axis,
        ve_map_state.ve_map,
    )

    ve_write_controller = VeWriteController(EVENT_SOUND)

    app_window.register_screen("home", home_screen)
    app_window.register_screen("dashboard", dashboard)
    app_window.register_screen("ve_calibration", ve_calibration_screen)
    app_window.show_screen("home")

    home_screen.screen_requested.connect(app_window.show_screen)

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

    app_window.key_event.connect(event_marker.handle_key)
    app_window.key_event.connect(space_detector.on_key_pressed)
    app_window.key_event.connect(ve_calibration_screen.handle_key)
    app_window.key_released.connect(space_detector.on_key_released)

    dashboard.key_event.connect(event_marker.handle_key)
    dashboard.key_event.connect(space_detector.on_key_pressed)
    dashboard.key_released.connect(space_detector.on_key_released)

    signal_processor = SignalProcessor()
    signal_processor.emitter.connect(dashboard.process_signals)
    signal_processor.emitter.connect(alarm_processor.process_signals)
    signal_processor.emitter.connect(vehicle_state.update)
    signal_processor.emitter.connect(lambda_loop_processor.process_signals)
    signal_processor.emitter.connect(ve_calibration_screen.process_signals)

    ve_calibration_screen.ve_adjustment_made.connect(ve_write_controller.on_adjustment_made)
    ve_write_controller.command_requested.connect(ecu_connection.send_command)
    ecu_connection.map_data_received.connect(ve_calibration_screen.receive_map_data)

    ecu_connection.emitter.connect(signal_processor.process_line)
    ecu_connection.emitter.connect(log_writer.write)
    ecu_connection.start()

    # Request breakpoints and full VE map from ECU on startup
    ecu_connection.send_command(EcuCommand.READ_RPM_BREAKPOINTS)
    ecu_connection.send_command(EcuCommand.READ_MAP_BREAKPOINTS)
    for row in range(16):
        ecu_connection.send_command(EcuCommand.ve_row(row))

    app_window.show()

    app.exec()

    app_window.close()
    alarm_processor.stop()
    ecu_connection.stop()


if __name__ == "__main__":
    main()
