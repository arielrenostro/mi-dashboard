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
from app.event.marker import EventMarker
from app.lifecycle import shutdown
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
        register_ecu_connection(EcuConnectionMock(config.connection.mock, config.connection.mock_skip_lines))
    else:
        register_ecu_connection(EcuConnectionSerial(config.connection.port, config.connection.baudrate))

    app_window = AppWindow(signal_processor)
    app_window.show()

    alarm_processor.emitter.connect(app_window.on_alarm_onset)

    event_marker = EventMarker(config.datalog.mark_sound)
    app_window.key_event.connect(event_marker.handle_key)
    event_marker.event_triggered.connect(log_writer.set_event_pending)

    get_ecu_connection_thread().error.connect(app_window.on_connection_error)
    get_ecu_connection().emitter.connect(signal_processor.process_line)
    get_ecu_connection().emitter.connect(log_writer.write)
    get_ecu_connection_thread().start()

    try:
        app.exec()
    finally:
        shutdown(app_window, get_ecu_connection_thread(), alarm_processor, log_writer)


if __name__ == "__main__":
    main()
