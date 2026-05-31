from PyQt6.QtCore import QThread

from app.ecu_connection.ecu_protocol import EcuProtocol


class EcuConnectionThread(QThread):

    def __init__(self, protocol: EcuProtocol):
        super().__init__()
        self.protocol = protocol

    def start(self, **kwargs):
        super().start(**kwargs)
        self.protocol.start()

    def stop(self):
        self.protocol.stop()

    def run(self):
        self.protocol.run()
