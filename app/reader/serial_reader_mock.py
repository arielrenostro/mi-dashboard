import time

from PyQt6.QtCore import QThread, pyqtSignal


class SerialReaderMock(QThread):
    emitter = pyqtSignal(str)

    def __init__(self, port, baudrate):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = True
        self.serial = None
        self.line = 0

    def connect(self):
        pass

    def run(self):
        self.connect()

        while self.running:
            with open(
                    "C:\\Users\\ariel\\OneDrive\\Carros\\206\\Master Injection\\Datalogs\\4Bar - 9\\log_stream_fixed.csv",
                    'r') as f:
                # for line in f:
                #     parts = line.split(';')
                #     try:
                #         map_ = int(parts[2])
                #         if map_ >= 100:
                #             break
                #     except:
                #         pass

                for line in f:
                    self.line += 1
                    if self.line < 12100:
                        continue
                    if not self.running:
                        break
                    self.emitter.emit(line.strip())
                    time.sleep(0.1)

    def stop(self):
        self.running = False
