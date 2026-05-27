import logging
import os
import sys
from datetime import datetime

from PyQt6.QtWidgets import QApplication

from app.alarm.processor import AlarmProcessor
from app.config import config
from app.ecu_connection import register_ecu_session
from app.ecu_connection.serial_transport import SerialTransport
from app.ecu_connection.mock_transport import MockTransport
from app.ecu_connection.session import EcuSession
from app.event.app_events import AppEventType
from app.event.bus import event_bus
from app.log_writer.log_writer import LogWriter
from app.logger import setup_logging
from app.masterinjection.signal_processor import SignalProcessor
from app.state.state import vehicle_state
from app.ui.window import AppWindow

logger = logging.getLogger(__name__)


def _get_log_file_path() -> str:
    return os.path.join(config.datalog.path, f'log_stream_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')


def main():
    setup_logging()
    logger.info("Starting app")

    app = QApplication(sys.argv)

    # Transport e Session
    if config.connection.mock != '':
        transport = MockTransport(config.connection.mock)
    else:
        transport = SerialTransport(config.connection.port, config.connection.baudrate)
    ecu_session = EcuSession(transport)
    register_ecu_session(ecu_session)

    # Processadores de dados (inscrevem no bus no próprio __init__)
    signal_processor = SignalProcessor()
    log_writer = LogWriter(log_file=_get_log_file_path())
    alarm_processor = AlarmProcessor(config.alarm.sound)

    # Subscrições sem dono natural
    event_bus.subscribe(AppEventType.SIGNALS_RECEIVED, lambda e: vehicle_state.update(e.data))
    event_bus.subscribe(AppEventType.ECU_COMMAND_REQUESTED, lambda e: ecu_session.send_command(e.command, e.args))

    # Keyboard actions (desativadas intencionalmente — manter comentado)
    # key_hold_detector = KeyHoldDetector(Qt.Key.Key_Space, hold_ms=2000)
    # lambda_toggle = LambdaToggle(config.ve_calibration)
    # event_marker = EventMarker(config.alarm.sound)
    # app_window.key_event.connect(key_hold_detector.on_key_pressed)
    # app_window.key_released.connect(key_hold_detector.on_key_released)
    # key_hold_detector.triggered.connect(lambda_toggle.handle_trigger)

    # UI
    app_window = AppWindow()   # sem parâmetro signal_processor
    app_window.show()

    # Iniciar comunicação (por último)
    ecu_session.start()

    app.exec()

    app_window.close()
    alarm_processor.stop()
    ecu_session.stop()


if __name__ == "__main__":
    main()
