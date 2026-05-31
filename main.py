import logging
import os
import sys
from datetime import datetime

from PyQt6.QtWidgets import QApplication

from app.alarm.processor import AlarmProcessor
from app.config import config
from app.ecu_connection import register_ecu_protocol, get_ecu_connection_thread
from app.ecu_connection.ecu_protocol import EcuProtocol
from app.ecu_connection.transport_mock import EcuTransportMock
from app.ecu_connection.transport_serial import EcuTransportSerial
from app.event.app_events import AppEventType
from app.event.bus import event_bus
from app.event.marker import EventMarker
from app.log_writer.log_writer import LogWriter
from app.logger import setup_logging
from app.masterinjection.signal_processor import SignalProcessor
from app.ui.window import AppWindow

logger = logging.getLogger(__name__)


def main():
    setup_logging()
    logger.info("Starting app")

    app = QApplication(sys.argv)

    # 1. Log writer — subscribes to ECU_FRAME_RECEIVED internally
    log_writer = LogWriter(
        log_file=os.path.join(config.datalog.path, f'log_stream_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'),
    )

    # 2. Alarm processor — subscribes to SIGNALS_RECEIVED internally
    alarm_processor = AlarmProcessor(config.alarm.sound)
    alarm_processor.start()

    # 3. Signal processor — subscribes to ECU_FRAME_RECEIVED internally
    signal_processor = SignalProcessor()

    # 4. VehicleState — subscribes to ECU_HANDSHAKE_COMPLETED, ECU_RESPONSE_RECEIVED,
    #    ECU_FRAME_RECEIVED, SIGNALS_RECEIVED internally (via state.py module-level singleton)
    from app.state.state import vehicle_state  # noqa: F401 — triggers subscription wiring

    # 5. Event marker (logs CSV marks on key press)
    event_marker = EventMarker(config.alarm.sound)
    event_bus.subscribe(
        event_type=AppEventType.EVENT_MARK_REQUESTED,
        callback=lambda _: log_writer.set_event_pending(),
    )

    # 6. ECU transport + protocol
    if config.connection.mock != '':
        transport = EcuTransportMock(config.connection.mock)
    else:
        transport = EcuTransportSerial(config.connection.port, config.connection.baudrate)

    protocol = EcuProtocol(transport)
    register_ecu_protocol(protocol)

    # 7. UI — connects screen_requested signals internally via _register_screen
    app_window = AppWindow(signal_processor)
    app_window.show()

    # 8. Keyboard handlers (currently disabled; uncomment to enable)
    # from app.event.key_hold_detector import KeyHoldDetector
    # from app.event.lambda_toggle import LambdaToggle
    # from PyQt6.QtCore import Qt
    # lambda_toggle = LambdaToggle(config.ve_calibration.ve_sound)
    # space_detector = KeyHoldDetector(Qt.Key.Key_Space, 2000)
    # space_detector.triggered.connect(lambda_toggle.handle_trigger)
    # app_window.key_event.connect(space_detector.on_key_pressed)
    # app_window.key_released.connect(space_detector.on_key_released)
    # app_window.key_event.connect(event_marker.handle_key)

    # 9. Start ECU thread (all subscribers already wired above)
    get_ecu_connection_thread().start()

    app.exec()

    app_window.close()
    alarm_processor.stop()
    get_ecu_connection_thread().stop()


if __name__ == "__main__":
    main()
