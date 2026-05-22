import logging
import time
from typing import Any, List

from app.ecu_connection import EcuConnection
from app.masterinjection.protocol import EcuCommand

logger = logging.getLogger(__name__)


class EcuConnectionMock(EcuConnection):

    def __init__(self, mock_file):
        super().__init__()
        self.mock_file = mock_file
        self.line = 0

    def send_command(self, cmd: EcuCommand, args: List[Any] | None = None) -> None:
        pass

    def run(self):
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

                logger.debug(f'Emitting mock line: {line}')
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

    def start(self, **kwargs):
        self.running = True

    def stop(self):
        self.running = False
