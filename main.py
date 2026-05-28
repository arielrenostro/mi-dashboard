import logging
import os
import sys
from datetime import datetime

from PyQt6.QtWidgets import QApplication

from app.alarm.processor import AlarmProcessor
from app.config import config
from app.ecu import register_ecu_session, get_ecu_session
from app.ecu.session import EcuSession
from app.ecu.transport import create_transport
from app.event.app_events import AppEventType
from app.event.bus import event_bus
from app.event.marker import EventMarker
from app.log_writer.log_writer import LogWriter
from app.logger import setup_logging
from app.masterinjection.signal_processor import SignalProcessor
from app.state.state import vehicle_state
from app.ui.window import AppWindow

logger = logging.getLogger(__name__)


def main():
    setup_logging()
    logger.info("Starting app")

    app = QApplication(sys.argv)

    # 1. LogWriter (subscribes to ECU_MESS_FRAME internally)
    log_writer = LogWriter(
        log_file=os.path.join(config.datalog.path, f'log_stream_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'),
    )

    # 2. AlarmProcessor (subscribes to SIGNALS_RECEIVED internally; no thread)
    alarm_processor = AlarmProcessor(config.alarm.sound)

    # 3. SignalProcessor (subscribes to ECU_MESS_FRAME internally)
    signal_processor = SignalProcessor()

    # 4. VehicleState: update on SIGNALS_RECEIVED
    event_bus.subscribe(
        event_type=AppEventType.SIGNALS_RECEIVED,
        callback=vehicle_state.update_signals,
    )

    # 5. Event mark
    event_marker = EventMarker(config.alarm.sound)
    event_bus.subscribe(
        event_type=AppEventType.EVENT_MARK_REQUESTED,
        callback=lambda _: log_writer.set_event_pending(),
    )

    # 6. EcuSession
    transport = create_transport()
    session = EcuSession(transport)
    register_ecu_session(session)

    # ECU_COMMAND_REQUESTED → session.send_command
    event_bus.subscribe(
        event_type=AppEventType.ECU_COMMAND_REQUESTED,
        callback=lambda e: session.send_command(e.command, e.args),
    )

    # 7. AppWindow
    app_window = AppWindow(signal_processor)
    app_window.show()

    # 8. Start I/O thread
    session.start()

    app.exec()

    app_window.close()
    alarm_processor.stop()
    session.stop()


if __name__ == "__main__":
    main()
