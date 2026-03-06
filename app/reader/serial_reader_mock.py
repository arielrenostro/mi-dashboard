import time

from PyQt6.QtCore import QThread, pyqtSignal


class SerialReaderMock(QThread):
    emitter = pyqtSignal(str)

    def __init__(self, mock_file):
        super().__init__()
        self.mock_file = mock_file
        self.line = 0
        self.running = True

    def connect(self):
        pass

    def run(self):
        while self.running:

            last_timestamp = None

            with open(self.mock_file, 'r') as f:
                log_origin = "master"
                line = f.readline().replace(',', ';').strip()

                if line.count(';') == 33:
                    log_origin = "this"

                for line in f:
                    self.line += 1
                    if not self.running:
                        break
                    if self.line < 12250:
                        continue
                    parts = line.split(';')
                    # map_ = int(parts[2])
                    # if map_ <= 100:
                    #     continue

                    self.emitter.emit(line.strip())

                    if log_origin == "this" and last_timestamp is not None:
                        try:
                            timestamp = int(parts[0])
                            time.sleep(timestamp - last_timestamp)
                            last_timestamp = timestamp
                            continue
                        except:
                            pass

                    time.sleep(0.1)
                    last_timestamp = time.time()

    def stop(self):
        self.running = False
