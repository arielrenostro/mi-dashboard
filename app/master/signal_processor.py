from PyQt6.QtWidgets import QWidget
from pyqtgraph.Qt.QtCore import Signal

from app.master.log import LOG_PREFIX
from app.master.signal import Signal as SignalEnum


class SignalProcessor(QWidget):
    emitter = Signal(dict)

    def __init__(self):
        super().__init__()

    def process_line(self, line):
        if not line.startswith(LOG_PREFIX):
            return

        parts = line.split(";")
        if len(parts) < 2:
            return

        parsed_data = dict()
        for signal in SignalEnum:
            try:
                if signal.value.get("calculated", False):
                    try:
                        raw = signal.value["value"](parsed_data)
                        value = raw
                    except:
                        raw = -1
                        value = -1
                else:
                    idx = signal.value["index"]
                    if idx >= len(parts):
                        continue
                    raw = parts[idx]
                    value = signal.value["converter"](raw)

                parsed_data[signal] = {
                    "signal": signal,
                    "raw": raw,
                    "value": value,
                    "value_str": signal.value["for_label"](value),
                }
            except Exception as e:
                print(e)
        self.emitter.emit(parsed_data)
