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
from app.event.app_events import AppEventType
from app.event.bus import event_bus
from app.event.marker import EventMarker
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
        log_file=os.path.join(config.datalog.path, f'log_stream_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'),
    )

    alarm_processor = AlarmProcessor(config.alarm.sound)
    alarm_processor.start()

    signal_processor = SignalProcessor()

    event_bus.subscribe(
        event_type=AppEventType.SIGNALS_RECEIVED,
        callback=lambda e: vehicle_state.update(e.data),
    )

    event_bus.subscribe(
        event_type=AppEventType.ECU_COMMAND_REQUESTED,
        callback=lambda e: get_ecu_connection().send_command(e.command, e.args),
    )

    event_marker = EventMarker(config.alarm.sound)
    event_bus.subscribe(
        event_type=AppEventType.EVENT_MARK_REQUESTED,
        callback=lambda _: log_writer.set_event_pending(),
    )

    if config.connection.mock != '':
        register_ecu_connection(EcuConnectionMock(config.connection.mock))
    else:
        register_ecu_connection(EcuConnectionSerial(config.connection.port, config.connection.baudrate))

    app_window = AppWindow(signal_processor)
    app_window.show()

    # lambda_toggle = LambdaToggle(config.ve_calibration.ve_sound)
    # space_detector = KeyHoldDetector(Qt.Key.Key_Space, 2000)
    # space_detector.triggered.connect(lambda_toggle.handle_trigger)
    # app_window.key_event.connect(space_detector.on_key_pressed)
    # app_window.key_released.connect(space_detector.on_key_released)
    # app_window.key_event.connect(event_marker.handle_key)

    get_ecu_connection().emitter.connect(signal_processor.process_line)
    get_ecu_connection().emitter.connect(log_writer.write)
    get_ecu_connection_thread().start()

    app.exec()

    app_window.close()
    alarm_processor.stop()
    get_ecu_connection_thread().stop()


if __name__ == "__main__":
    main()
