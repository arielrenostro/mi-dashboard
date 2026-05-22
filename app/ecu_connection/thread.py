from PyQt6.QtCore import QThread, pyqtSignal

from app.ecu_connection import EcuConnection


class EcuConnectionThread(QThread):
    emitter = pyqtSignal(str)

    def __init__(self, ecu_connection: EcuConnection):
        super().__init__()
        self.ecu_connection = ecu_connection
        self.ecu_connection.emitter = self.emitter
        self.running = False

    def start(self, **kwargs):
        super().start(**kwargs)
        self.running = True

    def stop(self):
        self.running = False
        self.ecu_connection.running = False

    def run(self):
        while self.running:
            self.ecu_connection.run()
