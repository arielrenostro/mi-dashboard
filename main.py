import logging
import os
import sys
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication
)

from app.alarm.processor import AlarmProcessor
from app.config import config
from app.ecu_connection import register_ecu_connection, get_ecu_connection, get_ecu_connection_thread
from app.ecu_connection.mock_log import EcuConnectionMock
from app.ecu_connection.serial import EcuConnectionSerial
from app.log_writer.log_writer import LogWriter
from app.logger import setup_logging
from app.masterinjection.signal_processor import SignalProcessor
from app.state.state import vehicle_state
from app.ui.window import AppWindow

logger = logging.getLogger(__name__)


# ==========================================
# MAIN
# ==========================================

def main():
    setup_logging()
    logger.info("Starting app")

    app = QApplication(sys.argv)

    log_writer = LogWriter(
        log_file=os.path.join(config.datalog.path, f'log_stream_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv'),
    )

    alarm_processor = AlarmProcessor(config.alarm.sound)
    alarm_processor.start()

    signal_processor = SignalProcessor()
    signal_processor.emitter.connect(alarm_processor.process_signals)
    signal_processor.emitter.connect(vehicle_state.update)

    if config.connection.mock != '':
        register_ecu_connection(EcuConnectionMock(config.connection.mock))
    else:
        register_ecu_connection(EcuConnectionSerial(config.connection.port, config.connection.baudrate))

    # TODO -> Registrar na instancia de dashboard
    # alarm_processor.emitter.connect(dashboard.fire_field_alarm)

    app_window = AppWindow(signal_processor)
    app_window.show()

    # dashboard = Dashboard(
    #     grid=GRID,
    #     graphs=GRAPH,
    #     graph_x_size=150,
    # )
    #
    # home_screen = HomeScreen()
    #
    # ve_calibration_screen = VeCalibrationScreen()
    # ve_calibration_screen.populate_ve_table(
    #     ve_map_state.rpm_axis,
    #     ve_map_state.map_axis,
    #     ve_map_state.ve_map,
    # )
    #
    # ve_write_controller = VeWriteController(EVENT_SOUND)

    # lambda_toggle = LambdaToggle(EVENT_SOUND)
    # lambda_toggle.command_requested.connect(ecu_connection.send_command)
    # lambda_toggle.command_requested.connect(lambda_loop_processor.on_command_received)
    #
    # space_detector = KeyHoldDetector(Qt.Key.Key_Space, 2000)
    # space_detector.triggered.connect(lambda_toggle.handle_trigger)

    # event_marker = EventMarker(EVENT_SOUND)
    # event_marker.event_triggered.connect(log_writer.set_event_pending)

    # app_window.key_event.connect(event_marker.handle_key)
    # app_window.key_event.connect(space_detector.on_key_pressed)
    # app_window.key_event.connect(ve_calibration_screen.handle_key)
    # app_window.key_released.connect(space_detector.on_key_released)

    # dashboard.key_event.connect(event_marker.handle_key)
    # dashboard.key_event.connect(space_detector.on_key_pressed)
    # dashboard.key_released.connect(space_detector.on_key_released)

    #
    # # Request breakpoints and full VE map from ECU on startup
    # ecu_connection.send_command(EcuCommand.RPM_BREAKPOINTS)
    # ecu_connection.send_command(EcuCommand.MAP_BREAKPOINTS)
    # for row in range(16):
    #     ecu_connection.send_command(EcuCommand.ve_row(row))

    get_ecu_connection().emitter.connect(signal_processor.process_line)
    get_ecu_connection().emitter.connect(log_writer.write)
    get_ecu_connection_thread().start()

    app.exec()

    app_window.close()
    alarm_processor.stop()
    get_ecu_connection_thread().stop()


if __name__ == "__main__":
    main()
