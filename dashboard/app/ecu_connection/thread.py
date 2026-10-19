import logging

from PyQt6.QtCore import QThread, pyqtSignal

from app.ecu_connection import EcuConnection

logger = logging.getLogger(__name__)


class EcuConnectionThread(QThread):
    emitter = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, ecu_connection: EcuConnection):
        super().__init__()
        self.ecu_connection = ecu_connection
        self.ecu_connection.emitter = self.emitter
        self.ecu_connection.error_emitter = self.error
        self.running = False

    def start(self, **kwargs):
        super().start(**kwargs)
        self.ecu_connection.start()
        self.running = True

    def stop(self, timeout_ms: int = 3000):
        """Stop the source and wait (bounded) for the thread to finish."""
        self.running = False
        self.ecu_connection.stop()
        if self.isRunning() and not self.wait(timeout_ms):
            logger.warning("ECU connection thread did not finish within %d ms; terminating it", timeout_ms)
            self.terminate()
            self.wait(1000)

    def run(self):
        while self.running:
            self.ecu_connection.run()
